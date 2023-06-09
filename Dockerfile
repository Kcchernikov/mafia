FROM python:3.11

WORKDIR /

COPY requirements.txt /

RUN pip install --upgrade pip -r requirements.txt

COPY . /

EXPOSE 9000

CMD ["python", "proxy.py"]
