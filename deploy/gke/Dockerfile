FROM python:3.11-slim

WORKDIR /app

# Install only the cloud controller dependencies
RUN pip install --no-cache-dir \
    pyyaml \
    kubernetes \
    requests

# Copy the symbolu package
COPY symbolu/ /app/symbolu/

# Controller runs on port 8080
EXPOSE 8080

ENTRYPOINT ["python", "-m", "symbolu.cloud_controller.main"]
CMD ["--config", "/etc/ncc/controller.yaml"]
