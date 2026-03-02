# 📘 Course Guide - How to Use This Course

Welcome to **Celery Production Mastery**! This guide explains how to navigate the course, complete labs, and get the most out of your learning experience.

---

## 🗺️ Course Structure

### Branch-Based Learning Model

This course uses **Git branches** as the primary learning mechanism. Each module is a separate branch that contains:

- ✅ Working code for that module's concepts
- ✅ Detailed README with theory and examples
- ✅ Hands-on lab exercises
- ✅ Test suite to validate your learning

### Why Branches?

**Benefits:**
- 📸 **Snapshots** - Each module is a complete, working state
- 🔄 **Reproducible** - Reset to any module anytime with `git checkout`
- 📈 **Progressive** - Each module builds on the previous
- 🧪 **Testable** - Run tests to verify understanding
- 🔖 **Bookmarkable** - Git tags mark stable checkpoints

**Example progression:**
```
master (you are here)
  ↓ git checkout section-0-baseline-environment
section-0-baseline-environment (v0-baseline)
  ↓ git checkout section-1-task-lifecycle
section-1-task-lifecycle (v1-architecture)
  ↓ git checkout section-2-worker-internals
section-2-worker-internals (v2-workers)
  ... continue through all 12 modules
```

---

## 🚦 Getting Started

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd celery-playground
```

### Step 2: Install Prerequisites

**Required:**
- Python 3.13+
- Docker & Docker Compose
- Git

**Optional (for later modules):**
- Kubernetes (minikube, kind, or k3s)
- kubectl

### Step 3: Start with Module 0

```bash
# Checkout the first module
git checkout section-0-baseline-environment

# Read the module README
cat README.md

# Install dependencies
pip install -e .

# Start infrastructure
docker-compose up -d

# Begin the labs!
```

---

## 📖 How to Complete a Module

Each module follows the same pattern:

### 1️⃣ Read the README

Every module's README contains:

```markdown
📚 Learning Objectives       # What you'll master
🎯 Key Concepts              # Theory with code examples
🔧 Changes in This Module    # What's new vs previous module
🔬 Lab Exercises             # Hands-on challenges
📊 Troubleshooting           # Common issues
📖 Reference                 # External docs
✅ Completion Checklist      # Self-assessment
```

**Pro tip:** Don't skip the "Key Concepts" section—it provides context for the labs.

### 2️⃣ Complete the Lab Exercises

Each lab follows this format:

#### Lab Structure

```markdown
### Lab X.1: [Name]

🎯 Goal: What you'll learn

🔧 Setup:
# Commands to run before the challenge

💪 Challenge: 
What you need to figure out or implement

💡 Hints (click to expand):
- Hint 1
- Hint 2

✅ Solution (click to expand):
Step-by-step solution with commands

✓ Verification:
- [ ] Checkpoint 1
- [ ] Checkpoint 2
```

#### How to Approach Labs

**Recommended workflow:**

1. **Read the goal** - Understand what you're trying to learn
2. **Run the setup** - Get the environment ready
3. **Try the challenge first** - Attempt without looking at hints
4. **Use hints if stuck** - Click to reveal progressive hints
5. **Check the solution** - Compare your approach
6. **Verify completion** - Run the verification steps

**Learning modes:**

- 🎓 **Learn mode** - Read solution first, then implement
- 💪 **Challenge mode** - Try first, use hints only when stuck (recommended)
- ⚡ **Speed mode** - Follow solution directly (not recommended for learning)

### 3️⃣ Run the Tests

Each module has validation tests:

```bash
# Run tests for current module
pytest tests/test_module_00*.py -v

# Run all tests (to ensure nothing broke)
pytest

# Run with coverage
pytest --cov=celery_playground --cov=demo --cov=production_patterns
```

**What tests validate:**
- ✅ Configuration is correct
- ✅ Tasks execute successfully
- ✅ Error handling works
- ✅ Production patterns are implemented correctly

### 4️⃣ Review the Completion Checklist

Before moving to the next module:

```markdown
✅ Module Completion Checklist
- [ ] All labs completed
- [ ] All tests passing
- [ ] Understand all code changes
- [ ] Can explain concepts to someone else
- [ ] Ready for next module
```

### 5️⃣ Move to Next Module

```bash
# Checkout the next branch
git checkout section-1-task-lifecycle

# Start over at step 1
```

---

## 🔧 Working with the Code

### Making Changes

**Option 1: Work in the branch directly**
```bash
git checkout section-X-module-name
# Make changes, experiment
# Reset when done: git checkout .
```

**Option 2: Create your own branch**
```bash
git checkout section-X-module-name
git checkout -b my-section-X-experiments
# Make changes safely
# Switch back: git checkout section-X-module-name
```

**Option 3: Stash your work**
```bash
# Save your work temporarily
git stash

# Switch modules
git checkout section-Y-next-module

# Return and restore your work
git checkout section-X-previous-module
git stash pop
```

### Resetting a Module

If you break something:

```bash
# Discard all changes
git checkout .

# Or reset completely
git reset --hard HEAD

# Or re-checkout the branch
git checkout section-X-module-name --force
```

---

## 🧪 Testing Your Work

### Test Categories

1. **Module tests** - Validate current module concepts
   ```bash
   pytest tests/test_module_03*.py
   ```

2. **Integration tests** - Validate entire system
   ```bash
   pytest tests/test_integration*.py
   ```

3. **Manual verification** - Some labs require manual inspection
   - Check logs
   - Inspect Redis keys
   - View Flower UI
   - Check Grafana dashboards

### Debugging Failed Tests

```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Run specific test
pytest tests/test_module_03_reliability.py::test_idempotency -v
```

---

## 📊 Module Dependencies

### Linear Path (Recommended)

Follow modules 0 → 1 → 2 → ... → 12 in order.

**Why?** Each module builds on previous concepts and code.

### Alternative Paths

If you have specific learning goals:

**Path 1: Reliability Focus**
- Module 0 → 1 → 3 → 4 → 6 → 9

**Path 2: Kubernetes Focus**
- Module 0 → 1 → 2 → 5 → 8 → 10

**Path 3: Advanced Patterns**
- Module 0 → 1 → 7 → 11

**Path 4: Observability Focus**
- Module 0 → 1 → 8 → 9

---

## 🎯 Lab Exercise Tips

### Understanding the Challenge

Each challenge is designed to make you **think** before coding:

❌ **Don't do this:**
- Immediately click "Solution"
- Copy-paste without understanding

✅ **Do this:**
- Read the goal carefully
- Think about what you already know
- Try your own approach first
- Use hints progressively
- Compare your solution with the provided one

### Using Hints Effectively

Hints are structured progressively:

```
💡 Hint 1: High-level direction
💡 Hint 2: Specific file or function
💡 Hint 3: Almost the answer
```

**Best practice:** Read one hint, try again, then move to next hint if still stuck.

### When You're Stuck

1. **Re-read the Key Concepts section** - Answer is often there
2. **Check the previous module** - Building on prior knowledge
3. **Review error messages** - They're very informative
4. **Check troubleshooting section** - Common issues listed
5. **Look at the solution** - Learning from good code is valid!

---

## 🛠️ Infrastructure Commands

### Docker Compose

```bash
# Start services
docker-compose up -d

# Start with specific config
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f redis
docker-compose logs -f worker

# Stop services
docker-compose down

# Clean up everything
docker-compose down -v  # Removes volumes too
```

### Celery Commands

```bash
# Start worker
celery -A celery_playground worker --loglevel=info

# Start worker for specific queue
celery -A celery_playground worker -Q critical --loglevel=info

# Start Beat (scheduler)
celery -A celery_playground beat --loglevel=info

# Start Flower (monitoring)
celery -A celery_playground flower --port=5555

# Inspect workers
celery -A celery_playground inspect active
celery -A celery_playground inspect stats
celery -A celery_playground inspect registered

# Purge all tasks
celery -A celery_playground purge
```

### Django Commands

```bash
# Run migrations
python manage.py migrate

# Create superuser (for admin)
python manage.py createsuperuser

# Django shell (test tasks manually)
python manage.py shell

# Run development server
python manage.py runserver
```

### Redis Commands

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# In Redis CLI:
KEYS celery*           # List all Celery keys
LLEN default           # Check queue length
MONITOR                # Watch all Redis commands
FLUSHALL               # Clear everything (careful!)
```

---

## 📚 Additional Resources

### In This Repository

- [`README.md`](../README.md) - Course overview and module index
- [`docs/production_checklist.md`](../docs/production_checklist.md) - Pre-deployment checklist
- [`docs/troubleshooting_guide.md`](../docs/troubleshooting_guide.md) - Common issues
- [`docs/production_settings_template.py`](../docs/production_settings_template.py) - Complete config reference

### External Documentation

- [Celery Docs](https://docs.celeryq.dev/) - Official documentation
- [Django-Celery-Beat](https://django-celery-beat.readthedocs.io/) - Scheduling
- [Redis Docs](https://redis.io/docs/) - Broker documentation
- [Flower Docs](https://flower.readthedocs.io/) - Monitoring

---

## ✅ Progress Tracking

### Self-Assessment

After each module, rate yourself:

- ⭐ - Completed labs, tests pass (minimal understanding)
- ⭐⭐ - Can explain concepts (good understanding)
- ⭐⭐⭐ - Can apply to real projects (mastery)

**Goal:** ⭐⭐⭐ on all modules before considering yourself production-ready.

### Completion Certificate

After completing all 12 modules and the production checklist:

```bash
# Run the complete validation suite
./scripts/validate_production_ready.sh

# If all checks pass, you're production-ready! 🎉
```

---

## 🤝 Getting Help

### Troubleshooting Steps

1. **Check the module's Troubleshooting section** in README
2. **Review error messages carefully** - They're usually clear
3. **Check Docker/Celery logs** - Most issues show up there
4. **Verify services are running** - `docker-compose ps`
5. **Check the troubleshooting guide** - Common issues documented

### Common Issues

See [`docs/troubleshooting_guide.md`](../docs/troubleshooting_guide.md) for solutions to:
- Connection refused errors
- Task not found errors
- Import errors
- Worker not consuming tasks
- Memory issues
- And more...

---

## 🎓 Learning Best Practices

### Time Management

- 📅 **Recommended pace:** 2-3 modules per week
- ⏰ **Time per module:** 1-3 hours
- 🎯 **Focus time:** Block distraction-free time for labs
- 🔁 **Spaced repetition:** Review previous modules periodically

### Active Learning

- ✍️ **Take notes** - Write down key insights
- 🗣️ **Explain to others** - Teaching reinforces learning
- 🔬 **Experiment** - Break things intentionally to understand them
- 🏗️ **Build projects** - Apply concepts to real problems

### Mastery Mindset

- 🐢 **Slow is smooth, smooth is fast** - Don't rush
- ❓ **Question everything** - Why does it work this way?
- 🔥 **Learn from failures** - Break things safely here, not in production
- 🎯 **Focus on patterns** - Understand the "why" behind best practices

---

## 🚀 Ready to Begin?

You now have everything you need to succeed in this course!

**Next steps:**

1. ✅ Read the [main README](../README.md) for course overview
2. ✅ Ensure prerequisites are installed
3. ✅ Checkout Module 0: `git checkout section-0-baseline-environment`
4. ✅ Start learning! 🎉

**Remember:** Every expert was once a beginner. Take your time, complete the labs, and you'll master production Celery.

---

**Questions not covered here?** Check the [Troubleshooting Guide](../docs/troubleshooting_guide.md) or open an issue.

Happy learning! 🚀

