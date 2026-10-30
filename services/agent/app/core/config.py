"""Configuration management for agent service."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent service settings."""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Service
    service_name: str = "agent"
    service_port: int = 8003
    log_level: str = "INFO"
    
    # Database
    database_url: str
    
    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "agentshield-demo"
    
    # Service token for calling gateway
    agent_service_token: str
    
    # Gateway
    gateway_url: str = "http://gateway:8000"
    
    # Ollama
    ollama_host: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_temperature: float = 0.2
    ollama_num_ctx: int = 4096
    ollama_timeout: int = 120
    
    # Agent budgets
    max_steps: int = 12
    max_tool_calls: int = 20
    max_replans: int = 2
    max_wall_seconds: int = 180
    max_llm_calls: int = 30
    
    # Mode
    agent_mode: str = "L0"  # L0=live, L3=replay
    replay_trace_path: str = "traces/demo_golden.json"
    
    # Features
    enable_memory: bool = True
    enable_tracing: bool = True


settings = Settings()
