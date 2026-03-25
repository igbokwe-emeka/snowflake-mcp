FROM python:3.10-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy requirements and install
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy agent code
COPY agent.py .
COPY snowflake_tools.py .

# Expose port (if needed for A2A direct access, though usually it connects out or uses a specific port)
EXPOSE 10000

# Run the agent using uvicorn (since to_a2a returns a FastAPI app)
# We need to install uvicorn in the agent image too if we want to run it directly
RUN uv pip install --system uvicorn

CMD ["uvicorn", "agent:a2a_app", "--host", "0.0.0.0", "--port", "10000"]
