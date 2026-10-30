FROM ghcr.io/vineetchoudhary/tuya-local-key:latest

WORKDIR /work

COPY pir_listener.py /work/pir_listener.py

CMD ["python", "/work/pir_listener.py"]