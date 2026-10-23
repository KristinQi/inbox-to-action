import streamlit as st
from google import genai
import os
import json
import re

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="Inbox → Action",
    page_icon="📥",
    layout="centered"
)

st.title("📥 Inbox → Action")
st.write("Turn messy work emails into clear, actionable next steps.")

st.caption(
    "AI interprets the email. You review the result. "
    "Only confirmed tasks are added to your to-do list."
)

# -----------------------------
# Gemini setup
# -----------------------------
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)
# -----------------------------
# Session state
# -----------------------------
if "extracted_tasks" not in st.session_state:
    st.session_state.extracted_tasks = []

if "todo_list" not in st.session_state:
    st.session_state.todo_list = []

# -----------------------------
# Helper functions
# -----------------------------
def clean_json_response(text):
    text = text.strip()

    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    return text.strip()


def assign_priority(task):
    timing = task.get("deadline_timing", "").lower()
    dependency = task.get("dependency", "").lower()

    if dependency not in ["", "none", "not specified"]:
        return "Waiting"

    if any(word in timing for word in ["today", "tomorrow", "asap", "urgent"]):
        return "High"

    if any(
        word in timing
        for word in [
            "friday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "this week",
        ]
    ):
        return "Medium"

    return "Low"


def analyze_email(email_text):
    prompt = f"""
You are an email-to-action extraction assistant.

Your job is to convert a work email into structured, actionable tasks.

IMPORTANT RULES:

1. Extract only tasks that the recipient is expected to perform.
2. Do not turn background information, greetings, compliments, or discussion
   statements into tasks.
3. A meeting or discussion should only become a standalone task if the recipient is explicitly asked to prepare, present, schedule, or complete something for it.
4. If a meeting or discussion only provides context or timing for another task, preserve it in the details or notes instead of creating a separate task.
5. Never invent a deadline.
6. If timing is vague, preserve the wording or write "Not specified".
7. If a task depends on another person, event, file, or decision, identify it.
8. A dependency is an unresolved prerequisite that prevents the recipient from starting or completing the task.

9. Do not treat documents, dashboards, datasets, files, reports, or other resources as dependencies if the email indicates they are already available.

10. Only identify a dependency when the recipient must wait for another person, event, approval, file delivery, confirmation, or decision before proceeding.

11. If a resource is already available and can be used immediately, dependency should be "None".
12. Preserve uncertainty. Never turn ambiguous language into a more certain instruction, deadline, or dependency than the email supports.



Before returning each task, check:
- Is this actually an action the recipient must perform?
- Is the deadline explicitly supported by the email?
- Is the dependency truly unresolved, or is it simply an available resource?
For each task return:

task
goal
deadline_timing
dependency
details
open_questions
evidence

Use this exact JSON structure:

{{
  "tasks": [
    {{
      "task": "",
      "goal": "",
      "deadline_timing": "",
      "dependency": "",
      "details": "",
      "open_questions": "",
      "evidence": ""
    }}
  ]
}}

EMAIL:

{email_text}
"""

    models_to_try = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite"
    ]

    last_error = None

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            cleaned = clean_json_response(response.text)
            return json.loads(cleaned)

        except Exception as e:
            last_error = e
            continue

    raise last_error

# -----------------------------
# Email input
# -----------------------------
email_text = st.text_area(
    "Paste your email",
    placeholder="Paste a work email here...",
    height=280
)

if st.button("Analyze Email", type="primary"):

    if not email_text.strip():
        st.warning("Please paste an email first.")

    else:
        try:
            with st.spinner("Analyzing email..."):
                result = analyze_email(email_text)

            st.session_state.extracted_tasks = result.get("tasks", [])
            if not st.session_state.extracted_tasks:
                st.session_state.no_tasks_found = True
            else:
                st.session_state.no_tasks_found = False
        except Exception as e:
            st.error(
                "The AI service could not complete the request. "
                "Please try again in a moment."
            )
            st.caption(str(e))


# -----------------------------
# Review extracted tasks
# -----------------------------
if st.session_state.get("no_tasks_found", False):
    st.success("✓ No actionable tasks detected.")
    st.caption("This email does not appear to require any action from you.")
if st.session_state.extracted_tasks:

    st.divider()
    st.subheader("Review extracted tasks")

    st.caption(
        "AI-generated suggestions — review and edit the information "
        "before adding tasks."
    )

    selected_tasks = []

    for i, task in enumerate(st.session_state.extracted_tasks):

        priority = assign_priority(task)

        with st.container(border=True):

            selected = st.checkbox(
                "Add this task",
                value=True,
                key=f"select_{i}"
            )

            edited_task = st.text_input(
                "Task",
                value=task.get("task", ""),
                key=f"task_{i}"
            )

            edited_goal = st.text_input(
                "Goal / Aim",
                value=task.get("goal", ""),
                key=f"goal_{i}"
            )

            edited_timing = st.text_input(
                "Deadline / Timing",
                value=task.get("deadline_timing", "Not specified"),
                key=f"timing_{i}"
            )

            edited_dependency = st.text_input(
                "Dependency",
                value=task.get("dependency", "None"),
                key=f"dependency_{i}"
            )

            priority_options = ["High", "Medium", "Waiting", "Low"]

            edited_priority = st.selectbox(
                "Priority",
                priority_options,
                index=priority_options.index(priority),
                key=f"priority_{i}",
                help="Suggested based on the email. You can change it before adding the task."
            )

            st.caption("AI-suggested priority — editable before adding to your to-do list.")

            edited_details = st.text_area(
                "Details",
                value=task.get("details", ""),
                key=f"details_{i}",
                height=80
            )
            edited_questions = st.text_area(
                "Open Questions / Notes",
                value=task.get("open_questions", "None"),
                key=f"questions_{i}",
                height=70
            )

            with st.expander("View source evidence"):
                st.write(task.get("evidence", "Not available"))

            if selected:
                selected_tasks.append(
                    {
                        "task": edited_task,
                        "goal": edited_goal,
                        "deadline_timing": edited_timing,
                        "priority": edited_priority,
                        "dependency": edited_dependency,
                        "status": "Not Started",
                        "details": edited_details,
                        "open_questions": edited_questions,
                        "evidence": task.get("evidence", "")
                    }
                )

    if st.button("Add Selected Tasks to To-Do List"):

        if selected_tasks:
            st.session_state.todo_list.extend(selected_tasks)
            st.session_state.extracted_tasks = []
            st.success("Tasks added to your to-do list.")
            st.rerun()

        else:
            st.warning("Please select at least one task.")


elif email_text and not st.session_state.extracted_tasks:
    pass


# -----------------------------
# To-do list
# -----------------------------
if st.session_state.todo_list:

    st.divider()
    st.subheader("My To-Do List")

    priority_order = {
        "High": 0,
        "Medium": 1,
        "Waiting": 2,
        "Low": 3
    }

    sorted_tasks = sorted(
        enumerate(st.session_state.todo_list),
        key=lambda x: priority_order.get(x[1]["priority"], 99)
    )

    for original_index, task in sorted_tasks:

        with st.container(border=True):

            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"### {task['task']}")

            with col2:
                st.write(f"**{task['priority']}**")

            st.write(
                f"**Deadline / Timing:** "
                f"{task['deadline_timing']}"
            )

            st.write(
                f"**Dependency:** "
                f"{task['dependency']}"
            )

            new_status = st.selectbox(
                "Status",
                ["Not Started", "In Progress", "Waiting", "Done"],
                index=[
                    "Not Started",
                    "In Progress",
                    "Waiting",
                    "Done"
                ].index(task["status"]),
                key=f"status_{original_index}"
            )

            st.session_state.todo_list[original_index]["status"] = new_status

            with st.expander("View task details"):

                st.write(f"**Goal / Aim:** {task['goal']}")

                st.write(f"**Details:** {task['details']}")

                st.write(
                    f"**Open Questions / Notes:** "
                    f"{task['open_questions']}"
                )

                st.write(
                    f"**Source Evidence:** "
                    f"{task['evidence']}"
                )

            if st.button(
                "Delete Task",
                key=f"delete_{original_index}"
            ):
                st.session_state.todo_list.pop(original_index)
                st.rerun()

else:
    st.divider()
    st.subheader("My To-Do List")
    st.info("No confirmed tasks yet.")
