# Claude Python SDK - Dockerized AI Agent

A dockerized FastAPI service that provides REST API access to Anthropic's Claude AI, designed to run on Unraid servers as a cloud AI agent.

## Features

- RESTful API wrapper for Claude AI
- Docker containerized for easy deployment
- Optimized for Unraid server deployment
- Health checks and monitoring
- Configurable model selection
- CORS support for web applications
- Resource limits and logging configuration
- Non-root container for security

## Prerequisites

- Docker and Docker Compose installed
- Anthropic API key ([Get one here](https://console.anthropic.com/))
- Unraid server (or any Docker-compatible system)

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Proxy-Python-SDK
```

### 2. Configure Environment Variables

Copy the example environment file and edit it with your settings:

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```env
ANTHROPIC_API_KEY=your_actual_api_key_here
```

### 3. Deploy with Docker Compose

```bash
docker-compose up -d
```

The service will be available at `http://localhost:8000`

## Unraid Deployment

### Method 1: Using Community Applications (Recommended)

1. Open Unraid Web UI
2. Go to Docker tab
3. Click "Add Container"
4. Fill in the following:
   - **Name**: `claude-sdk-agent`
   - **Repository**: Build from your repository or use pre-built image
   - **Network Type**: `bridge`
   - **Port**: `8000` (Container) → `8000` (Host)
   - **Environment Variables**:
     - `ANTHROPIC_API_KEY`: Your API key
     - `DEFAULT_MODEL`: `claude-sonnet-4-5-20250929`
     - `MAX_TOKENS`: `4096`
     - `LOG_LEVEL`: `info`

### Method 2: Using Docker Compose (via terminal/SSH)

1. SSH into your Unraid server
2. Navigate to `/mnt/user/appdata/claude-sdk/`
3. Clone this repository there
4. Create `.env` file with your configuration
5. Run `docker-compose up -d`

### Method 3: Building Custom Template

Create a template XML file in `/boot/config/plugins/dockerMan/templates-user/`:

```xml
<?xml version="1.0"?>
<Container version="2">
  <Name>claude-sdk-agent</Name>
  <Repository>claude-python-sdk:latest</Repository>
  <Network>bridge</Network>
  <WebUI>http://[IP]:[PORT:8000]</WebUI>
  <Port>
    <HostPort>8000</HostPort>
    <ContainerPort>8000</ContainerPort>
    <Protocol>tcp</Protocol>
  </Port>
  <Variable>
    <Name>ANTHROPIC_API_KEY</Name>
    <Mode/>
    <Value/>
  </Variable>
  <Variable>
    <Name>DEFAULT_MODEL</Name>
    <Mode/>
    <Value>claude-sonnet-4-5-20250929</Value>
  </Variable>
</Container>
```

## API Endpoints

### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "claude-proxy-sdk",
  "version": "1.0.0"
}
```

### Chat with Claude

```bash
POST /chat
```

Request body:
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Hello, Claude!"
    }
  ],
  "model": "claude-sonnet-4-5-20250929",
  "max_tokens": 1024,
  "temperature": 1.0,
  "system": "You are a helpful assistant."
}
```

Response:
```json
{
  "id": "msg_123abc",
  "role": "assistant",
  "content": "Hello! How can I assist you today?",
  "model": "claude-sonnet-4-5-20250929",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 20
  }
}
```

### List Available Models

```bash
GET /models
```

## Usage Examples

### Using cURL

```bash
# Health check
curl http://localhost:8000/health

# Send a message to Claude
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'
```

### Using Python

```python
import requests

# Chat with Claude
response = requests.post(
    "http://localhost:8000/chat",
    json={
        "messages": [
            {"role": "user", "content": "Explain quantum computing in simple terms"}
        ],
        "max_tokens": 500
    }
)

result = response.json()
print(result["content"])
```

### Using JavaScript/Node.js

```javascript
const response = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    messages: [
      { role: 'user', content: 'Tell me a joke' }
    ]
  })
});

const data = await response.json();
console.log(data.content);
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (required) | - |
| `HOST` | Server host address | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `DEFAULT_MODEL` | Default Claude model to use | `claude-sonnet-4-5-20250929` |
| `MAX_TOKENS` | Default maximum tokens in response | `4096` |
| `TEMPERATURE` | Default temperature for responses | `1.0` |
| `SERVICE_NAME` | Service identifier | `claude-proxy-sdk` |
| `LOG_LEVEL` | Logging level (debug, info, warning, error) | `info` |

### Available Claude Models

- `claude-sonnet-4-5-20250929` - Claude Sonnet 4.5 (Most advanced)
- `claude-3-7-sonnet-20250219` - Claude 3.7 Sonnet (Powerful and balanced)
- `claude-3-5-haiku-20241022` - Claude 3.5 Haiku (Fast and efficient)
- `claude-3-opus-20240229` - Claude 3 Opus (Previous generation)

## Monitoring and Maintenance

### View Logs

```bash
# View real-time logs
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100
```

### Check Container Status

```bash
docker-compose ps
```

### Restart Service

```bash
docker-compose restart
```

### Update Service

```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

## Resource Usage

The default configuration limits:
- **CPU**: Up to 2 cores (0.5 cores reserved)
- **Memory**: Up to 2GB (512MB reserved)

Adjust in `docker-compose.yml` based on your Unraid server capacity.

## Security Considerations

1. **API Key Protection**: Never commit your `.env` file to version control
2. **Network Security**: Consider using a reverse proxy (nginx, Traefik) with SSL
3. **Access Control**: Implement authentication if exposing to the internet
4. **Firewall**: Configure Unraid firewall rules appropriately
5. **Non-root User**: Container runs as non-root user for enhanced security

## Troubleshooting

### Container won't start

```bash
# Check logs for errors
docker-compose logs

# Verify environment variables
docker-compose config
```

### API returns 503 errors

- Verify `ANTHROPIC_API_KEY` is set correctly
- Check Anthropic API status
- Review logs: `docker-compose logs claude-sdk`

### High memory usage

- Reduce `MAX_TOKENS` in configuration
- Lower the memory limits in `docker-compose.yml`
- Monitor concurrent requests

### Connection refused

- Ensure port 8000 is not already in use
- Check firewall rules on Unraid
- Verify container is running: `docker ps`

## Development

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
```

### Testing API

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the [Anthropic documentation](https://docs.anthropic.com/)
- Review Docker and Unraid documentation

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Powered by [Anthropic Claude](https://www.anthropic.com/)
- Designed for [Unraid](https://unraid.net/)
