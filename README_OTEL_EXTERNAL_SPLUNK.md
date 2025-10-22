# OpenTelemetry + External Splunk Setup

Este setup permite usar um servidor Splunk externo para coletar telemetria do SKIP Server via OpenTelemetry.

## 🏗️ Arquitetura

```
Skip Server → OTEL Collector → External Splunk
     ↓              ↓               ↓
  - Logs         - Processing    - Analysis
  - Traces       - Batching      - Dashboards
  - Metrics      - Filtering     - Alerting
```

## 🔧 Configuração

### 1. Configure o Splunk Externo

Primeiro, inicie seu Splunk externo usando o docker-compose dedicado:

```bash
# Iniciar Splunk externo
docker-compose -f docker-compose_splunk.yml up -d

# Verificar se está rodando
docker-compose -f docker-compose_splunk.yml ps
```

### 2. Configure as Variáveis de Ambiente

Edite o arquivo `.env` para apontar para seu Splunk externo:

```env
# External Splunk Configuration
SPLUNK_HEC_ENDPOINT=http://host.docker.internal:8088
SPLUNK_HEC_TOKEN=12345678-1234-1234-1234-123456789012
```

**Para Splunk em outra máquina:**
```env
SPLUNK_HEC_ENDPOINT=http://IP_DO_SPLUNK:8088
```

### 3. Iniciar o Stack de Aplicação

```bash
# Build e iniciar SKIP Server + OTEL Collector
docker-compose -f docker-compose_otel.yml up --build -d

# Verificar logs
docker-compose -f docker-compose_otel.yml logs -f
```

## 📊 Acesso e Monitoramento

- **Skip Server**: http://localhost:8080
- **OTEL Collector Metrics**: http://localhost:8888/metrics
- **Splunk UI**: http://localhost:8000 (se rodando localmente)

## 🔍 Validação

### 1. Verificar conectividade do OTEL Collector

```bash
# Logs do collector
docker logs otel-collector

# Deve mostrar: "Everything is ready. Begin running and processing data."
```

### 2. Verificar dados no Splunk

No Splunk, execute:

```spl
# Verificar se dados estão chegando
index=main sourcetype="otel:*" | head 10

# Verificar logs da aplicação
index=main sourcetype="otel:logs" service.name="skip-server"
```

## 🐛 Troubleshooting

### Problema: OTEL Collector não consegue conectar no Splunk

**Sintoma:** Logs mostram "connection refused" ou timeouts

**Soluções:**
1. Verificar se Splunk está rodando: `docker ps | grep splunk`
2. Verificar se HEC está habilitado no Splunk
3. Verificar token HEC no Splunk
4. Para Splunk em outra máquina, verificar firewall

### Problema: Dados não aparecem no Splunk

**Sintoma:** Queries no Splunk retornam vazias

**Soluções:**
1. Verificar index configurado (`main`)
2. Verificar sourcetype (`otel:logs`, `otel:traces`)
3. Verificar time range no Splunk
4. Verificar logs do OTEL Collector

### Problema: Performance lenta

**Soluções:**
1. Aumentar batch size no `otel-collector-config.yaml`
2. Aumentar timeout do Splunk HEC
3. Configurar mais workers no collector

## 📝 Configurações Avançadas

### Múltiplos Ambientes

Para diferentes ambientes, crie arquivos `.env` específicos:

```bash
# Desenvolvimento
docker-compose -f docker-compose_otel.yml --env-file .env.dev up -d

# Produção  
docker-compose -f docker-compose_otel.yml --env-file .env.prod up -d
```

### Configuração de Rede Customizada

Para usar rede externa:

```yaml
networks:
  otel-network:
    external: true
    name: my-monitoring-network
```

### TLS/SSL para Splunk

Para Splunk com HTTPS:

```env
SPLUNK_HEC_ENDPOINT=https://splunk.company.com:8088
```

E adicionar certificados no OTEL Collector se necessário.

## 🔄 Backup e Restore

Os logs locais ficam em `./logs/` como backup mesmo com OTEL ativo.

Para restore, configure data retention no Splunk conforme necessário.