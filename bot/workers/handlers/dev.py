import asyncio
import html
import io
import sys
import traceback

from bot import bot, log_file_name
from bot.utils.bot_utils import split_text
from bot.utils.log_utils import logger
from bot.utils.msg_utils import get_args, user_is_dev, user_is_owner
from bot.utils.os_utils import read_n_to_last_line, s_remove


async def get_logs(event, args, client):
    if not user_is_owner(event.from_user.id):
        return
    try:
        if not args:
            await event.reply_document(
                document=log_file_name,
                quote=True,
                caption=log_file_name,
            )
            return
        arg = get_args("-t", to_parse=args)
        if arg.t and arg.t.isdigit() and (ind := int(arg.t)):
            msg = str()
            for i in reversed(range(1, ind)):
                msg += read_n_to_last_line(log_file_name, i)
                msg += "\n"
            msg = "Nothing Here.\nTry with a higher number" if not msg else msg
            pre_event = event
            for smsg in split_text(msg):
                smsg = f"\n{smsg}\n"
                pre_event = await pre_event.reply(smsg, quote=True, link_preview=False)
                await asyncio.sleep(2)
        else:
            return await get_logs(event, None, client)

    except Exception:
        await logger(Exception)
        await event.reply("`An error occurred.`")


async def aexec(code, event):
    exec(f"async def __aexec(event): " + "".join(f"\n {l}" for l in code.split("\n")))
    return await locals()["__aexec"](event)


async def bash(event, cmd, client):
    """
    Run bash/system commands in bot
    Much care must be taken especially on Local deployment

    USAGE:
    Command requires executables as argument
    For example "/bash ls"
    """
    if not user_is_owner(event.from_user.id):
        if not user_is_dev(event.from_user.id):
            return
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    e = stderr.decode()
    if not e:
        e = "No Error"
    o = stdout.decode()
    if not o:
        o = "Tip:\nIf you want to see the results of your code, I suggest printing them to stdout."
    OUTPUT = f"QUERY:\n__Command:__\n{cmd} \n__PID:__\n{process.pid}\n\nstderr: \n{e}\nOutput:\n{o}"
    if len(OUTPUT) > 4000:
        with io.BytesIO(str.encode(OUTPUT)) as out_file:
            await event.reply_document(
                document=out_file.getvalue(),
                file_name="exec.text",
                quote=True,
                caption=cmd,
            )
            await asyncio.sleep(3)
            return
    else:
        OUTPUT = f"```bash\n{cmd}```\n\n_PID:_\n{process.pid}\n\n```Stderr:\n{e}```\n\n```Output:\n{html.escape(o)}```\n"
        await event.reply(OUTPUT, link_preview=False)


async def aexec2(code, client, message):
    exec(
        f"async def __aexec2(client, message): "
        + "".join(f"\n {l}" for l in code.split("\n"))
    )
    return await locals()["__aexec2"](client, message)


async def eval_message(message, cmd, client):
    """
    Evaluate and execute code within bot.
    Global namespace has been cleaned so you'll need to manually import modules

    USAGE:
    Command requires code to execute as arguments.
    For example /peval print("Hello World!")
    Kindly refrain from adding whitelines and newlines between command and argument.
    """
    if not user_is_owner(message.from_user.id):
        if not user_is_dev(message.from_user.id):
            return
    status_message = await message.reply("Processing ...")

    old_stderr = sys.stderr
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    redirected_error = sys.stderr = io.StringIO()
    stdout, stderr, exc = None, None, None

    try:
        await aexec2(cmd, client, message)
    except Exception:
        exc = traceback.format_exc()

    stdout = redirected_output.getvalue()
    stderr = redirected_error.getvalue()
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    evaluation = ""
    if exc:
        evaluation = exc
    elif stderr:
        evaluation = stderr
    elif stdout:
        evaluation = stdout
    else:
        evaluation = "Success"

    final_output = "```python\n{}```\n\n```Output:\n{}```\n".format(
        cmd, evaluation.strip()
    )

    if len(final_output) > bot.max_message_length:
        final_output = "Evaluated:\n{}\n\nOutput:\n{}".format(cmd, evaluation.strip())
        with open("eval.text", "w+", encoding="utf8") as out_file:
            out_file.write(str(final_output))
        await message.reply_document(
            document="eval.text",
            caption=cmd,
            quote=True,
        )
        s_remove("eval.text")
        await asyncio.sleep(3)
        await status_message.delete()
    else:
        await status_message.edit(final_output)
