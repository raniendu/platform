"""
Prefect flow definitions.

This directory contains all Prefect flow definitions for the project.
Each flow module should define one or more @flow decorated functions.

Requirements: 7.1

Running Flows Locally:
    1. Start the local environment:
       ./scripts/local-up.sh

    2. Run a flow directly:
       python flows/<your_flow>.py

    3. Or deploy and run via Prefect:
       python scripts/deploy-flows.py  # Register deployments
       prefect deployment run '<your-flow>/<your-deployment>'  # In another

    4. View flow runs in the UI:
       http://localhost:4200
"""
