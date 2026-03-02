# 🎓 Celery Production Mastery Course

**Complete Engineering Handbook · Django · Redis · Kubernetes**

---

## 📊 Course Stats

| Modules | Labs | Production Patterns | K8s Configs |
|---------|------|---------------------|-------------|
| **12** | **24+** | **40+** | **10+** |

---

## 🎯 What You'll Learn

This is a comprehensive, hands-on course that takes you from Celery basics to production-grade distributed task processing. Through 12 progressive modules, you'll master:

- **Architecture decisions** - When to use Celery (and when not to)
- **Worker internals** - Concurrency models, prefetch, acknowledgments
- **Reliability patterns** - Idempotency, retries, time limits, failure handling
- **Queue architecture** - Multi-queue design, routing, isolation
- **Memory management** - Preventing OOMKills, profiling, recycling
- **Observability** - Monitoring, logging, distributed tracing
- **High availability** - Redis Sentinel, zero-downtime deployments
- **Kubernetes deployment** - HPA, graceful shutdown, production patterns
- **Advanced workflows** - Canvas, task versioning, distributed locks

By the end, you'll be able to design, deploy, and operate Celery at scale with confidence.

---

## 📚 Course Modules

### 🏗️ Foundation (Modules 0-3)

| Module | Branch | Topics | Duration |
|--------|--------|--------|----------|
| **0** | [section-0-baseline-environment](../../tree/section-0-baseline-environment) | Architecture Decisions, 10 Golden Rules | 1 hour |
| **1** | [section-1-task-lifecycle](../../tree/section-1-task-lifecycle) | Message Flow, Serialization, Result Backends | 2 hours |
| **2** | [section-2-worker-internals](../../tree/section-2-worker-internals) | Concurrency Models, Prefetch, Acknowledgment | 2 hours |
| **3** | [section-3-reliability](../../tree/section-3-reliability) | Idempotency, Retries, Time Limits, Dead Letters | 3 hours |

### ⚙️ Operations (Modules 4-7)

| Module | Branch | Topics | Duration |
|--------|--------|--------|----------|
| **4** | [section-4-backpressure](../../tree/section-4-backpressure) | Backpressure, Rate Control, Circuit Breakers | 2 hours |
| **5** | [section-5-queue-isolation](../../tree/section-5-queue-isolation) | Multi-Queue Architecture, Routing, Workload Isolation | 2 hours |
| **6** | [section-6-memory-management](../../tree/section-6-memory-management) | OOM Prevention, Profiling, Worker Recycling | 2 hours |
| **7** | [section-7-beat-scheduling](../../tree/section-7-beat-scheduling) | Django-Celery-Beat, Dynamic Schedules, Beat HA | 2 hours |

### 🚀 Production (Modules 8-11)

| Module | Branch | Topics | Duration |
|--------|--------|--------|----------|
| **8** | [section-8-monitoring](../../tree/section-8-monitoring) | Flower, Prometheus, Grafana, OpenTelemetry, Tracing | 3 hours |
| **9** | [section-9-redis-ha](../../tree/section-9-redis-ha) | Redis Production Config, Sentinel, Failure Scenarios | 2 hours |
| **10** | [section-10-kubernetes](../../tree/section-10-kubernetes) | K8s Deployment, HPA/KEDA, Graceful Shutdown | 3 hours |
| **11** | [section-11-advanced](../../tree/section-11-advanced) | Canvas Workflows, Task Versioning, Distributed Locks | 2 hours |

### ✅ Final Module

| Module | Branch | Topics | Duration |
|--------|--------|--------|----------|
| **12** | [section-12-production-ready](../../tree/section-12-production-ready) | Production Checklist, Deployment Guide, CI/CD | 1 hour |

**Total Course Duration:** ~28 hours of hands-on learning

---

## 🚀 Getting Started

### Prerequisites

Before starting this course, ensure you have:

- ✅ **Python 3.13+** installed
- ✅ **Docker & Docker Compose** installed and running
- ✅ **Basic Django knowledge** (models, views, settings)
- ✅ **Basic Celery concepts** (tasks, workers, brokers)
- ✅ **Git** for branch navigation
- ✅ **(Optional)** Kubernetes cluster (minikube/kind/k3s) for Modules 10-11

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd celery-playground

# Start with Module 0
git checkout section-0-baseline-environment

# Follow the README in that branch
cat README.md

# Install dependencies
pip install -e .

# Start Redis
docker-compose up -d

# Run your first Celery worker
celery -A celery_playground worker --loglevel=info
```

---

## 📖 How to Use This Course

### Branch-Based Learning

Each module is a **Git branch** that builds on the previous module:

```
master (start here - course overview)
  ↓
section-0-baseline-environment (Git tag: v0-baseline)
  ↓
section-1-task-lifecycle (Git tag: v1-architecture)
  ↓
section-2-worker-internals (Git tag: v2-workers)
  ↓
... (continue through all 12 modules)
```

### Learning Path

1. **Read the module README** - Each branch has a detailed README with:
   - Learning objectives
   - Key concepts explained
   - Code changes from previous module
   - Hands-on lab exercises

2. **Complete the labs** - Each module includes 2-4 hands-on exercises:
   - Setup instructions
   - Challenge to solve
   - Hints (expandable)
   - Solution (expandable)
   - Verification steps

3. **Run the tests** - Validate your understanding:
   ```bash
   pytest tests/test_module_XX*.py
   ```

4. **Move to next module** - Once all labs pass:
   ```bash
   git checkout section-X-next-module
   ```

### Lab Exercise Format

Each lab follows this pattern:

📋 **Goal** → 🔧 **Setup** → 💪 **Challenge** → 💡 **Hints** → ✅ **Solution** → ✓ **Verify**

See [COURSE_GUIDE.md](./COURSE_GUIDE.md) for detailed instructions.

---

## 🛠️ Development Setup

### Using Docker (Recommended)

```bash
# Start all services (Redis + Flower)
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run migrations
python manage.py migrate

# Start Redis (in separate terminal)
docker-compose up redis

# Start Celery worker (in separate terminal)
celery -A celery_playground worker --loglevel=info

# Start Django dev server (in separate terminal)
python manage.py runserver
```

---

## 📚 Additional Resources

### Reference Documentation

- [Production Settings Template](./docs/production_settings_template.py) - Complete production config
- [Worker Commands Reference](./docs/worker_commands_reference.md) - All worker CLI options
- [Production Checklist](./docs/production_checklist.md) - 24-item pre-deployment checklist
- [Troubleshooting Guide](./docs/troubleshooting_guide.md) - Common issues and solutions
- [Failure Scenarios](./docs/failure_scenarios.md) - What happens when things break

### External Links

- [Celery Official Documentation](https://docs.celeryq.dev/)
- [Django-Celery-Beat](https://django-celery-beat.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)
- [KEDA Documentation](https://keda.sh/) (for Kubernetes autoscaling)

---

## ✅ The 10 Production Golden Rules

Before you start, memorize these rules. Every module reinforces them:

| # | Rule | Why It Matters |
|---|------|----------------|
| **1** | Tasks MUST be idempotent | They will run more than once. Design for it. |
| **2** | Always enable `acks_late=True` | Otherwise a crashed worker = a lost task. |
| **3** | `prefetch_multiplier=1` for long tasks | Default=4 causes invisible task starvation. |
| **4** | `visibility_timeout` > max task duration | Redis will re-queue running tasks if timeout is too short. |
| **5** | Separate queues by workload type | One slow task type must never starve fast tasks. |
| **6** | Set time limits on every task | Tasks that hang will freeze a worker forever. |
| **7** | Use JSON serializer only, never pickle | pickle = arbitrary code execution vulnerability. |
| **8** | Run exactly one Beat instance | Two Beats = every scheduled task runs twice. |
| **9** | Monitor queue depth and failure rate | Silent failures are the most dangerous failures. |
| **10** | `terminationGracePeriod` > max task duration | Kubernetes rolling updates will kill tasks mid-flight. |

These aren't suggestions—they're the difference between a stable system and 3am pages.

---

## 🎯 Learning Outcomes

By completing this course, you will be able to:

- ✅ Design Celery architectures that scale to millions of tasks/day
- ✅ Prevent the most common production failures (task loss, memory leaks, duplicate execution)
- ✅ Monitor and debug Celery systems with comprehensive observability
- ✅ Deploy Celery to Kubernetes with zero-downtime updates
- ✅ Handle backpressure, rate limiting, and circuit breaking
- ✅ Implement advanced patterns (workflows, task versioning, distributed locks)
- ✅ Pass a production readiness review with confidence

---

## 🤝 Contributing

Found an issue? Have a suggestion? Contributions are welcome!

- Report bugs via GitHub Issues
- Submit improvements via Pull Requests
- Share your production patterns

---

## 📄 License

This course is provided for educational purposes. Code examples are MIT licensed.

---

## 🌟 Course Philosophy

**"Every line of code in this course represents a production incident that happened to someone, somewhere."**

We don't teach theory—we teach battle-tested patterns that prevent 3am pages. Each module addresses real failure modes with production-grade solutions.

**Ready to master production Celery?** 

👉 Start with [Module 0: Architecture Decisions](../../tree/section-0-baseline-environment)

---

**Questions?** See the [Course Guide](./COURSE_GUIDE.md) or [Troubleshooting Guide](./docs/troubleshooting_guide.md)

