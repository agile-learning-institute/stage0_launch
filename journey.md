# Stage0 Launch System – Context Summary

## Core Philosophy
Stage0 Launch is designed to help teams move from idea → working system quickly, without sacrificing software craftsmanship.  
The key belief: **speed without quality leads to failure**.

## Key Principles
- Developer Experience is critical to product success.
- Software craftsmanship enables sustainable velocity.
- AI-assisted development ("vibecoding") still requires engineers and discipline.
- The biggest risk in software is failing to reach a usable MVP.

## Design → Launch Workflow
Stage0 follows a structured pipeline:

1. **Design Phase**
   - Design workshops with stakeholders and engineers
   - Capture observations and workflows
   - Translate into structured specifications

2. **Specification Phase**
   - Architect converts observations into formal YAML specs
   - Specs define domains, data, and system structure

3. **Launch Phase**
   - Templates + specs are merged
   - A functional application is generated

## System Architecture Approach
- Microservice architecture with **bounded domains**
- Each service aligns to a **user experience or workflow**
- API-driven services with SPA frontend (BFF pattern)
- Poly-repo structure for independent deployability
- Mongo-style data domains (collection-oriented ownership)

This architecture is optimized for:
- AI code assistants (clear boundaries, focused context)
- Incremental iteration and scaling
- Contract-driven development

## Umbrella Repository Structure
Stage0 produces a central “umbrella repo” containing:
- Product overview and roadmap
- Developer onboarding guides
- CLI tooling and engineering standards
- Design specifications (YAML)
- Task framework for AI coding workflows
- Research and workshop outputs

## What Stage0 Produces
The generated system is:

- Functional and runnable locally (Docker)
- Built with strong engineering practices
- Includes automated CI/CD pipelines
- End-to-end tested
- Structured for rapid iteration
- A **starting point**, not a finished product

## What Stage0 Does NOT Do
- Not a fully production-ready product
- Not highly customized or branded
- Not a replacement for engineers
- Not a complete system

## Mission Control Vision (Relevant to This Product)
Stage0 enables products like Mission Control:
- Expose CI/CD and infrastructure workflows via APIs
- Drive workflows through interfaces like Discord bots
- Support product management, testing, and operations workflows
- Integrate with LLM-driven automation

## How to Use This GPT
This CustomGPT acts as a **Stage0 Architect**:
- Guides users from idea → architecture
- Defines bounded service domains and data models
- Produces specification files (architecture.yaml, catalog.yaml, product.yaml)
- Prepares systems for Stage0 Launch generation

Final step:
Use the generated specifications to run the Stage0 Launch process and create a working system.

(*Page 9: CustomGPT → Specs → Launch*)