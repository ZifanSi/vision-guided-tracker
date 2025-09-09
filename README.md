# High Performance Vision-Guided Camera Tracker  

**Developer Names**: Zifan Si, Jianqing Liu, Mike Chen, Xiaotian Lou  
**Supervisor**: TBD  

Date of project start: September 8th 2025  

**Project Overview**: The goal of this project is to design and implement a deployable camera tracking system capable of autonomously locking onto and following extremely fast-moving small targets, such as model rockets. The system integrates computer vision, motion control, and a web-based operator interface to deliver smooth, stable video (1080p @ 60fps) of critical rocket events such as staging and parachute deployment.  

This project builds a software stack that interfaces with low-cost hardware for small-scale launches (200m apogee) and is scalable to support the McMaster Rocketry Team’s high-powered rockets (3km+ apogee).  

---

### **Key Features**  

1. **Embedded Motion Control (STM32 + Rust)**  
   - Real-time two-axis gimbal control.  
   - Kalman filter for predictive object tracking.  
   - Serial communication with Jetson for closed-loop feedback.  

2. **Computer Vision Pipeline (NVIDIA Jetson Orin Nano + Python)**  
   - Object detection/tracking using CNN/Transformer models.  
   - Handles occlusion, downsampling, and interpolation for fast targets.  
   - Manual object selection and priority lock-in.  
   - Feedback control to embedded gimbal system.  

3. **Web Application (React + Flask)**  
   - Live video preview of camera feed.  
   - Operator controls for manual override and tracking parameter tuning.  
   - Start/stop video recording, playback, and download.  
   - REST API + WebSocket backend for communication.  

4. **System Integration & Deployment**  
   - End-to-end real-time rocket tracking at 1080p/60fps.  
   - CI/CD with GitHub Actions.  
   - Automated unit and integration tests.  
   - Dockerized builds for NVIDIA Jetson.  

---

The folders and files for this project are as follows:  

**docs** - Project documentation, design notes, diagrams  
**refs** - Reference materials (papers, hardware specs, related work)  
**src** - Source code for embedded system, CV pipeline, and web app  
**test** - Test cases, simulation data, and validation results  
