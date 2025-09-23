# Problem Statement and Goals Directory

This directory contains the problem statement and goals documentation for the RoCam project, a high-performance vision-guided rocket tracker. It defines the project’s motivation, scope, environment, and success criteria.

---

## Directory Contents

### Files
- `README.md` — Documentation overview  
- `ProblemStatement.tex` — LaTeX source for the Problem Statement and Goals document  
- `ProblemStatement.pdf` — Generated Problem Statement and Goals document  

---

## Major Components

### Problem Statement
- Identifies the challenges in model rocketry (staging failures, parachute tangling, high-speed tracking).  
- Defines system inputs and outputs (camera feed, gimbal control, video preview and recording).  
- Specifies performance objectives (support 1080p 60fps, real-time preview at ≥15fps).  

### Stakeholders
- **Direct**: McMaster Rocketry Team, Supervisor (Dr. Shahin Sirouspour).  
- **Indirect**: Aerospace researchers, event organizers, robotics community, potential industry users.  

### Environment
- **Deployment Environment**: Outdoor launch sites with variable conditions; lab testing; scaling to high-power launches.  
- **Execution Environment**: Hardware (gimbal + camera, STM32, Jetson, browser laptop) and software (baremetal STM32 code, Jetson with JetPack 6, web frontend).  

### Goals
- Primary: Track small-scale model rockets (<200m apogee) while meeting all performance objectives.  
- Stretch: 4K 60fps support, advanced zoom/focus control, integration with full-size gimbal, tracking up to 3km+ apogee flights.  

### Extras
- Circuit design for gimbal control.  
- User instructional video for end users.  

---

## Usage Guidelines

### Document Generation
- Compile `ProblemStatement.tex` to produce `ProblemStatement.pdf`.  
- Track revision history directly in the LaTeX source.  
- If a `Makefile` is provided in the parent directory, run `make` to generate documentation.  

### Plan Usage
- Use the problem statement to define project scope.  
- Refer to performance objectives when testing.  
- Adjust stretch goals and extras based on project feasibility.
