from app_pkg import app, socketio

if __name__ == '__main__':
    print('running server...')
    print('CTRL+C and refresh webpage to exit...')
    socketio.run(app)

