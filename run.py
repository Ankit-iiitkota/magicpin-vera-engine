import os
import uvicorn

if __name__ == '__main__':
    try:
        port_str = os.environ.get('PORT')
        port = int(port_str) if port_str and port_str.strip() else 8080
    except ValueError:
        port = 8080
    uvicorn.run('vera.main:app', host='0.0.0.0', port=port, workers=1)
