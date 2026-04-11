"""Launcher that runs both Discord bots concurrently as separate subprocesses.

Bots:
  - Guild Manager Bot  (guild_monitor_bot.py)   — uses GUILD_MONITOR_BOT_TOKEN
  - Guild Bot          (new_guild_bot/reconcile_bot.py) — uses TOKEN
"""

import asyncio
import subprocess
import sys


async def run_process(name: str, cmd: list[str]) -> int:
    """Start a subprocess and stream its output, returning its exit code."""
    print(f"🚀 Starting {name}: {' '.join(cmd)}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def stream_output():
        assert process.stdout is not None
        async for line in process.stdout:
            print(f"[{name}] {line.decode(errors='replace').rstrip()}", flush=True)

    await stream_output()
    await process.wait()
    return process.returncode


async def main():
    print("=" * 60)
    print("  Bot Launcher — starting both Discord bots")
    print("=" * 60)

    python = sys.executable

    guild_manager_task = asyncio.create_task(
        run_process("GuildManagerBot", [python, "guild_monitor_bot.py"]),
        name="GuildManagerBot",
    )
    guild_bot_task = asyncio.create_task(
        run_process("GuildBot", [python, "new_guild_bot/reconcile_bot.py"]),
        name="GuildBot",
    )

    print("✅ Both bots launched — waiting for either to exit...")

    # Block until the first bot exits, then cancel the other and shut down.
    done, pending = await asyncio.wait(
        {guild_manager_task, guild_bot_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in done:
        name = task.get_name()
        try:
            code = task.result()
            print(f"⚠️  {name} exited with code {code} — shutting down launcher")
        except Exception as exc:
            print(f"⚠️  {name} raised an exception: {exc} — shutting down launcher")

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
