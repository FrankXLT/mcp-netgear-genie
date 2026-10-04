FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache curl

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

ENV NETGEAR_HOST=http://192.168.100.1
ENV NETGEAR_USERNAME=admin
ENV NETGEAR_PASSWORD=password
ENV NETGEAR_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "mcp_netgear_genie.server"]
