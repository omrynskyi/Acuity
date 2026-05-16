# Acuity Kanban System: AI Agent Skill Guide

This guide describes how an AI agent should interact with the Acuity Kanban system to discover, acquire, and complete work.

## System Overview
The Acuity system is a task-based workflow managed via a FastAPI backend. Tasks are organized into sections and may have dependencies on other tasks.

**Base URL**: `http://localhost:8000`

---

## 1. Discovery: Finding Work

An agent should always start by finding the most relevant or actionable task.

### Get Next Actionable Task
Returns the first task that is currently in `todo` status and has all its dependencies met.
- **Endpoint**: `GET /api/next`
- **Use Case**: When you are ready to pick up a new task and don't have a specific ID in mind.

### Search for Tasks
Search by specific ID or partial text.
- **Endpoint**: `GET /api/search?id=<task_id>`
- **Endpoint**: `GET /api/search?name=<partial_name>`
- **Use Case**: When searching for a specific feature or verifying the status of a known task.

### View All Tasks
- **Endpoint**: `GET /api/tasks`

---

## 2. Acquisition: Locking a Task

Before performing any work, an agent **must** acquire a lock on the task. This prevents race conditions with other agents.

- **Endpoint**: `POST /api/tasks/{task_id}/acquire`
- **Body**: `{"agent": "your_agent_name"}`
- **Success (200 OK)**: Returns a `lock_token`. **Store this token safely**; it is required for completion.
- **Failure (400/409)**: If the task is blocked by dependencies or already locked, the API will return a descriptive error message.

---

## 3. Execution & Context

Once a task is acquired, read the details to understand the scope.

### Fetch Task Details
- **Endpoint**: `GET /api/tasks/{task_id}`
- **Context Fields**:
  - `description`: Detailed explanation of the task.
  - `acceptance_criteria`: Requirements to consider the task "done".

---

## 4. Completion: Finalizing the Task

After the work is finished and verified, mark the task as done to unblock dependent tasks.

- **Endpoint**: `POST /api/tasks/{task_id}/complete`
- **Body**: `{"lock_token": "your_stored_token"}`
- **Effect**: Moves the task to the `done` column and releases the lock.

### Releasing a Task (Failure/Abort)
If you cannot complete a task for any reason, release it so another agent can try.
- **Endpoint**: `POST /api/tasks/{task_id}/release`
- **Body**: `{"lock_token": "your_stored_token"}`

---

## Standard Agent Workflow (Summary)

1. **Find**: Call `GET /api/next` to find the highest priority actionable task.
2. **Acquire**: Call `POST /api/tasks/{id}/acquire` with your name. Store the `lock_token`.
3. **Read**: Call `GET /api/tasks/{id}` to get the `description` and `acceptance_criteria`.
4. **Work**: Execute the required engineering steps (write code, tests, etc.).
5. **Complete**: Call `POST /api/tasks/{id}/complete` with your `lock_token`.
