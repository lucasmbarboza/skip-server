FROM python:3.13-slim

RUN apt-get update && apt-get upgrade -y && apt-get clean

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080

CMD [ "python", "./skip_server.py" ]
