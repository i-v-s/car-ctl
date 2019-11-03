import json
from aiohttp.web import Application, run_app, RouteTableDef, Request, Response, json_response
from asyncio import Queue, create_subprocess_shell, create_task, subprocess, set_event_loop, sleep, gather
from dominate import document
from dominate.tags import meta, div, script
from dominate.util import raw
import RPi.GPIO as GPIO


routes = RouteTableDef()
queue = Queue(5)
f_pin, b_pin, l_pin, r_pin = [None] * 4


@routes.get('/')
async def index(request: Request):
    doc = document(title='Онлайн')
    with doc.head:
        meta(charset="utf-8")
        meta(http_equiv="X-UA-Compatible", content="IE=edge")
        meta(name="viewport", content="width=device-width, initial-scale=1")
    with doc:
        div(id='main', style='width: 100vw; height: 100vh;')
        script(raw('''
            const main = document.getElementById('main');
            let x = null, y = null;
            main.onmousedown = e => {
                x = e.screenX;
                y = e.screenY;
            }
            main.onmouseup = e => {
                x -= e.screenX;
                y -= e.screenY;
                fetch('/go?x=' + encodeURIComponent(-x) + '&y=' + encodeURIComponent(y), {method: 'PUT'});
            }
        '''))
    return Response(body=str(doc), content_type='text/html')


@routes.put('/go')
async def go(request: Request):
    query = request.rel_url.query
    x, y = float(query['x']) / 500, float(query['y']) / 500
    if queue.full():
        return json_response({'result': 'full'})
    await queue.put((x, y))
    return json_response({'result': 'ok'})


async def go_forward(y):
    global f_pin, b_pin
    if y:
        pin = f_pin
        if y < 0:
            pin = b_pin
            y = -y
        GPIO.output(pin, True)
        await sleep(y)
    GPIO.output(f_pin, False)
    GPIO.output(b_pin, False)


async def go_right(x):
    global r_pin, l_pin
    if x:
        pin = r_pin
        if x < 0:
            pin = l_pin
            x = -x
        GPIO.output(pin, True)
        await sleep(x)
    GPIO.output(r_pin, False)
    GPIO.output(l_pin, False)


async def go_task():
    while True:
        try:
            x, y = await queue.get()
            print(f'go {x},{y}')
            await gather(go_forward(y), go_right(x))
        except Exception as e:
            print(f'Go task exception: {e}')


async def run_go_task(app):
    create_task(go_task())


def main():
    global r_pin, l_pin, f_pin, b_pin
    GPIO.setmode(GPIO.BOARD)
    app = Application()
    app.add_routes(routes)
    with open('conf.json', 'r') as file:
        conf = json.load(file)
    r_pin, l_pin, f_pin, b_pin = conf['r_pin'], conf['l_pin'], conf['f_pin'], conf['b_pin']
    for pin in [r_pin, l_pin, f_pin, b_pin]:
        try:
            GPIO.setup(pin, GPIO.OUT, initial=False)
        except Exception as e:
            print(f'Initialize pin {pin}: {e}')
            return

    app.on_startup.append(run_go_task)
    port = conf['port']
    run_app(app, port=port)


if __name__ == '__main__':
    main()
