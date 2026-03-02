# ECS / FastAPI Implementation

This directory contains the FastAPI layer that was used before the Lambda refactor.

If traffic grows beyond ~100K users/month or streaming becomes a hard requirement,
this is the path back to ECS Fargate.

## To run
    uvicorn main:app --reload --port 8080

## Dependencies
All FastAPI deps are in requirements.txt in this directory.
Core business logic lives in factory/core/ — shared with Lambda.
