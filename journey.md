# StageZero Launch – Background Context

## Overview

**StageZero Launch** is a framework for rapidly launching a software product while maintaining strong engineering quality and craftsmanship.

The system emphasizes strong engineering practices, developer experience, and structured workflows that work well with modern AI code assistants.

---

# Core Principles

### Your product is only as good as your engineering team

Key ideas:

* **Developer Experience** is a key ingredient for a profitable product.
* **Software craftsmanship** creates a delightful developer experience.
* **Vibe coding does not mean removing engineers**, and it should not compromise craftsmanship.
* **Product launch** — the time from idea to MVP — is the biggest graveyard in software.

StageZero focuses on improving this launch phase.

---

# StageZero Design–Launch Framework

The framework separates the process into **Design** and **Launch** phases.

## Design Phase

Participants:

* Engineering Team
* Facilitator

Process:

1. Conduct a **Design Workshop**
2. Capture **Observations**

The workshop allows the engineering team to explore ideas collaboratively and record observations that guide system design.

---

## Launch Phase

Participants:

* Architect

Process:

1. Convert observations into **Specifications**
2. Apply **Templates**
3. **Merge** templates with specifications
4. Produce a **Functional Application**

The goal is to quickly generate a working system that provides a structured starting point for development.

---

# StageZero Umbrella Repository

StageZero is implemented using an **umbrella repository** that contains system-wide information and tooling.

Typical structure:

```
README.md
CONTRIBUTING.md
Makefile
/DeveloperEdition
/Research
/Specifications
/Tasks
/Workshops
```

Descriptions:

**README.md**
Product overview and implementation roadmap.

**CONTRIBUTING.md**
Developer onboarding process.

**Makefile**
Developer commands for running StageZero launch workflows.

**/DeveloperEdition**
Developer CLI and engineering standards.

**/Research**
A location for engineers to share research and technical findings.

**/Specifications**
Design specifications written as YAML files.

**/Tasks**
A task framework designed for use with LLM code assistants.

**/Workshops**
Observations captured from design workshops.

---

# StageZero Post-Launch Philosophy

Launching a system is only the beginning.

> Launch is not orbit.

Generated code should be considered:

* Functional (it does something)
* Well crafted
* Well tested
* Packaged for automated CI
* A starting point for rapid iteration

Generated code is **not**:

* Highly customized or branded
* A production-ready MVP
* Everything required for a finished product

---

# Future StageZero Services (“Mission Control”)

Post-launch services may include:

### Automation & LLM Integration

* Long-running LLM workflows integrated into automation systems
* Async pub/sub architecture templates
* Cloud deployment templates and runbooks (e.g., Terraform)

### MCP + Bot Integration

# Architecture Strategy

StageZero tools are **technology agnostic**, but templates define specific implementations.

Changes to architecture can be introduced by creating new templates.

---

## Demo Architecture

The reference demo system uses a **microservice architecture**:

Frontend:

* VueJS web applications

Backend:

* Python RESTful APIs

Database:

* MongoDB

---

## Why Microservices Work Well with AI Code Assistants

Microservices align well with LLM-based development because they create:

* Small independently deployable services
* Clearly defined bounded domains
* Contract-based interfaces
* Smaller code contexts for AI reasoning

AI assistants can:

* Consume engineering standards
* Read utility documentation
* Focus on one service or domain at a time

---

## Long-Running LLM Coding Tasks

StageZero repositories include a **Tasks framework** designed to support long-running LLM-assisted coding workflows.

This enables structured collaboration between engineers and AI coding assistants.