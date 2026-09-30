"""
Log Simulator — generates realistic test incidents.

Sends a mix of normal and anomalous log entries to the backend
at configurable intervals. Used for testing and demos.

Configuration (environment variables):
    BACKEND_URL:      Backend API base URL (default: http://localhost:8000)
    SIMULATOR_APP_ID: UUID of the app to send logs to (auto-creates if empty)
    ANOMALY_RATE:     Fraction of logs that are anomalies (default: 0.2)
    INTERVAL_SECONDS: Seconds between log batches (default: 10)
"""

import asyncio
import logging
import os
import random
import sys
from datetime import datetime, timezone

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("log_simulator")

# ── Configuration ──────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SIMULATOR_APP_ID = os.getenv("SIMULATOR_APP_ID", "")
# Sent as X-API-Key on ingestion if the backend has API_KEY protection enabled.
API_KEY = os.getenv("API_KEY", "")
ANOMALY_RATE = float(os.getenv("ANOMALY_RATE", "0.2"))
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "10"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))

# ── Realistic Log Templates ───────────────────────────────────────────

NORMAL_LOGS = [
    "INFO: Successfully processed request in {latency}ms — GET /api/v1/users",
    "INFO: User {user_id} authenticated successfully via OAuth2",
    "DEBUG: Cache hit for key user:profile:{user_id} — TTL 3600s remaining",
    "INFO: Health check passed — all 5 dependency checks OK",
    "INFO: Scheduled job 'cleanup_sessions' completed — removed {count} expired sessions",
    "INFO: Database migration check — schema up to date (version 47)",
    "DEBUG: Request processed — method=GET path=/api/v1/products status=200 duration={latency}ms",
    "INFO: WebSocket connection established — client {client_id} subscribed to channel 'updates'",
    "INFO: Rate limiter — bucket 'api_global' at {rate}% capacity — 847/{limit} requests",
    "DEBUG: Background worker 'email_sender' — processed 12 messages in {latency}ms",
    "INFO: SSL certificate check — expires in {days} days — cert=*.api.example.com",
    "INFO: Load balancer health — all {count} upstream servers healthy",
    "DEBUG: Redis connection pool — active: 8, idle: 42, total: 50",
    "INFO: CDN cache ratio — 94.7% hit rate over last 5 minutes",
    "INFO: Deployment verification — v2.14.3 running on 8/8 instances",
]

ANOMALY_LOGS = [
    # Database issues
    "FATAL: terminating connection due to administrator command — PostgreSQL connection pool exhausted after 30s, auth-service unable to process requests",
    "ERROR: ConnectionTimeout — Database connection pool exhausted, max_connections=50 reached in user-service, {count} queries waiting",
    "ERROR: DatabaseError — deadlock detected in transaction 0x{txid} — payment-service.process_order conflicting with inventory-service.update_stock",
    "CRITICAL: PostgreSQL replication lag exceeded 120s — replica db-replica-02 falling behind primary, read queries returning stale data",

    # Memory issues
    "ERROR: OutOfMemoryError — Java heap space in UserService.processRequest — allocated 2048MB, used 2047MB, GC overhead 98%",
    "CRITICAL: OOMKilled — Container 'api-gateway' killed by kernel OOM killer — RSS 4.2GB exceeded cgroup limit 4GB",
    "ERROR: OutOfMemoryError — Node.js heap out of memory in report-generator — FATAL ERROR: Reached heap limit Allocation failed",

    # Null/code errors
    "ERROR: NullPointerException at AuthController.validateToken line 142 — token payload missing 'sub' claim after JWT decode",
    "ERROR: TypeError — Cannot read properties of undefined (reading 'userId') at OrderService.createOrder:89 — missing request body validation",
    "ERROR: UnhandledException — IndexError: list index out of range in RecommendationEngine.predict() line 234",

    # HTTP/API errors
    "ERROR: 500 Internal Server Error — Unhandled exception in PaymentProcessor.chargeCard — Stripe API returned unexpected response format",
    "ERROR: 502 Bad Gateway — upstream service 'inventory-service' returned invalid response — connection reset by peer",
    "ERROR: 503 Service Unavailable — Circuit breaker OPEN for notification-service — 15 failures in last 60s, threshold: 10",

    # Infrastructure
    "CRITICAL: FATAL: terminating connection due to administrator command — PostgreSQL primary failover initiated, all connections dropped",
    "ERROR: ConnectionRefused — Redis sentinel at 10.0.1.{ip}:26379 unreachable — failover in progress, cache operations degraded",
    "CRITICAL: Kubernetes pod 'api-deployment-7f8b9c-{pod}' CrashLoopBackOff — restarted 5 times in 10 minutes, last exit code 137 (OOMKilled)",

    # Security
    "WARNING: RateLimitExceeded — IP {ip_addr} exceeded 1000 requests/minute threshold on /api/v1/auth/login — potential brute force attack",
    "ERROR: AuthenticationFailure — 47 failed login attempts for user admin@example.com in last 5 minutes from IP {ip_addr}",
    "CRITICAL: SSLCertificateExpired — TLS certificate for *.api.example.com expired 2 hours ago — HTTPS connections failing",

    # Performance
    "WARNING: SlowQuery — SELECT query on users table took {slow_ms}ms (threshold: 1000ms) — missing index on email column, full table scan detected",
    "ERROR: RequestTimeout — GET /api/v1/reports/generate timed out after 30s — report-service unresponsive, 23 requests queued",
    "WARNING: HighLatency — p99 response time 4.7s (SLA: 2s) — downstream dependency catalog-service responding slowly",
]

SERVICES = [
    "auth-service", "user-service", "payment-service", "order-service",
    "inventory-service", "notification-service", "api-gateway",
    "report-service", "search-service", "recommendation-engine",
]


def _generate_log(is_anomaly: bool) -> str:
    """Generate a single realistic log line with random parameters."""
    if is_anomaly:
        template = random.choice(ANOMALY_LOGS)
    else:
        template = random.choice(NORMAL_LOGS)

    # Fill in template variables
    return template.format(
        latency=random.randint(5, 450),
        user_id=f"usr_{random.randint(10000, 99999)}",
        client_id=f"ws_{random.randint(1000, 9999)}",
        count=random.randint(3, 200),
        rate=random.randint(20, 85),
        limit=random.choice([500, 1000, 2000, 5000]),
        days=random.randint(5, 90),
        txid=f"{random.randint(0x100000, 0xFFFFFF):x}",
        ip=random.randint(1, 254),
        ip_addr=f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        pod=f"{random.choice('abcdef')}{random.randint(1000,9999)}",
        slow_ms=random.randint(1500, 15000),
    )


def _generate_batch(batch_size: int, anomaly_rate: float) -> list[str]:
    """Generate a batch of log lines with the configured anomaly rate."""
    logs = []
    for _ in range(batch_size):
        is_anomaly = random.random() < anomaly_rate
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        service = random.choice(SERVICES)
        log_line = _generate_log(is_anomaly)
        logs.append(f"{timestamp} [{service}] {log_line}")
    return logs


async def _ensure_app_exists(client: httpx.AsyncClient) -> str:
    """Ensure the simulator app exists, create it if not."""
    global SIMULATOR_APP_ID

    if SIMULATOR_APP_ID:
        return SIMULATOR_APP_ID

    # Try to create the app
    try:
        response = await client.post(
            f"{BACKEND_URL}/api/v1/apps",
            json={
                "name": "log-simulator-app",
                "description": "Auto-created by log simulator for testing",
            },
        )
        if response.status_code == 200:
            data = response.json()
            app_id = data["data"]["id"]
            logger.info(f"Created simulator app: {app_id}")
            SIMULATOR_APP_ID = app_id
            return app_id
        elif response.status_code == 409:
            # App already exists, fetch it
            list_response = await client.get(f"{BACKEND_URL}/api/v1/apps")
            if list_response.status_code == 200:
                apps = list_response.json()["data"]["apps"]
                for app in apps:
                    if app["name"] == "log-simulator-app":
                        SIMULATOR_APP_ID = app["id"]
                        logger.info(f"Using existing simulator app: {SIMULATOR_APP_ID}")
                        return SIMULATOR_APP_ID
    except Exception as e:
        logger.error(f"Failed to ensure app exists: {e}")

    raise RuntimeError("Could not create or find simulator app")


async def run_simulator() -> None:
    """Main simulator loop — generates and sends logs continuously."""
    logger.info(
        f"Starting log simulator\n"
        f"  Backend URL:  {BACKEND_URL}\n"
        f"  Anomaly Rate: {ANOMALY_RATE * 100}%\n"
        f"  Interval:     {INTERVAL_SECONDS}s\n"
        f"  Batch Size:   {BATCH_SIZE}"
    )

    # Wait for backend to be ready
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(30):
            try:
                resp = await client.get(f"{BACKEND_URL}/health")
                if resp.status_code == 200:
                    logger.info("Backend is ready")
                    break
            except Exception:
                pass
            logger.info(f"Waiting for backend... (attempt {attempt + 1}/30)")
            await asyncio.sleep(3)
        else:
            logger.error("Backend not available after 90s, exiting")
            return

        # Ensure app exists
        try:
            app_id = await _ensure_app_exists(client)
        except RuntimeError as e:
            logger.error(str(e))
            return

        logger.info(f"Sending logs to app {app_id}")

        # Main loop
        batch_count = 0
        while True:
            try:
                logs = _generate_batch(BATCH_SIZE, ANOMALY_RATE)
                anomaly_count = sum(
                    1 for log in logs
                    if any(kw in log.lower() for kw in ["error", "fatal", "critical", "exception", "timeout"])
                )

                response = await client.post(
                    f"{BACKEND_URL}/api/v1/logs/ingest",
                    json={
                        "app_id": app_id,
                        "logs": logs,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    headers={"X-API-Key": API_KEY} if API_KEY else None,
                )

                batch_count += 1
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    logger.info(
                        f"[batch:{batch_count}] Sent {len(logs)} logs "
                        f"({anomaly_count} anomalies) — "
                        f"queued={data.get('queued_for_analysis', 0)}"
                    )
                else:
                    logger.warning(
                        f"[batch:{batch_count}] Ingest returned {response.status_code}: "
                        f"{response.text[:200]}"
                    )

            except httpx.TimeoutException:
                logger.warning(f"[batch:{batch_count}] Request timed out")
            except Exception as e:
                logger.error(f"[batch:{batch_count}] Error: {e}")

            await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_simulator())
