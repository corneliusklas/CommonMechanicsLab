# 🤖 Common Mechanics Lab

**An open robotics and AI learning platform by [Common Mechanics](https://commonmechanics.org)**  
Bringing together creativity, education, and real-world technology.  
Built to empower schools, makers, and researchers to explore robotics and artificial intelligence —  
without complicated setup or restrictive software.

---

## 🌍 Vision

We believe technology should be **accessible, understandable, and inspiring**.  
Common Mechanics Lab connects **hardware, software, and AI** into one modular ecosystem.  

From visual coding in Scratch to AI-driven robotic systems —  
everything is designed to be easy to start with, but powerful enough to grow into complex projects.

---

## 🧩 Core Concepts

- 🎨 **Visual coding in Scratch / TurboWarp** — ideal for education and creativity  
- 🐍 **Python backend** for AI, speech, and advanced control logic  
- 📡 **ESP32 controllers** manage sensors, motors, LEDs, and custom hardware  
- 🍓 **Raspberry Pi** serves as a hub, running the web interface, Python services, and AI tools  
- 🔊 **Audio I/O** through Raspberry Pi or connected devices (microphones, speakers)  
- 🌐 **WebSocket + HTTP communication** for fast real-time updates between all components  
- 🧠 **Local or cloud AI integration** (Whisper, Piper, OpenAI, or custom models)  
- 💡 **ROS 2 compatibility planned** for advanced robotics and research  
- ⚙️ **OTA updates** to easily deploy new firmware to ESP devices

---

## 🏗️ System Architecture

![System Diagram](docs/system_overview.png)

### Components Overview

| Component | Description |
|------------|--------------|
| **Scratch / TurboWarp** | User interface for programming robots and AI behavior |
| **Raspberry Pi Server** | Hosts the Scratch extensions, Python services, and web UI |
| **ESP32 Controllers** | Handle local sensors, actuators, motors, and lights |
| **Python Services** | Provide AI features (speech, text, vision) and interface logic |
| **Smart Devices (optional)** | Integration with Wi-Fi speakers, smart plugs, or cameras |
| **Client Devices** | Laptops, tablets, or classroom computers that connect via Wi-Fi |

---

## 🔊 Audio & AI

Common Mechanics Lab supports flexible audio input/output setups:
- Use the **laptop microphone** and stream to the Raspberry Pi for processing  
- Or connect **local Pi microphones and speakers** for standalone operation  
- AI services handle **speech-to-text**, **text-to-speech**, and **LLM-based dialogues**

All communication between Scratch, Python, and AI modules is handled securely over WebSocket and HTTP.

---

## 🔧 Hardware Support

- **ESP32 (Standard, CAM, Audio, or M5Stack variants)**  
- **Raspberry Pi 4 / 5** for local hosting and AI tasks  
- **Smart Home Devices** (optional): Shelly, Tuya Local, Tasmota-compatible plugs, etc.  
- **Custom Robotics Hardware:** servo arms, sensors, robot heads, and educational prototypes  

---

## 💰 Sustainability & Funding

Common Mechanics is designed to be **open and community-driven**,  
but sustainable through optional services and hardware sales:

- Educational kits and ready-to-use robots  
- Hosting and cloud AI integration  
- Workshops, teacher training, and customization for schools  
- Optional licensing for commercial or research use

---

## 🧠 Example Projects

- 🗣️ **Talking Robot Head:** animated eyes and mouth, speech recognition and response  
- 🎨 **Interactive Art Installations:** camera-based interaction, servo movement, lights  
- 🦾 **Robotic Arm Simulator:** Scratch control + ROS integration  
- 🏠 **Mini Smart Factory:** AI-assisted design to laser-cut and assemble small items  
- 🚀 **Creative Robots for Students:** cardboard, 3D printed, or mixed-material bots

---

## 🧰 Technical Roadmap

- [x] WebSocket-based ESP control  
- [x] Python AI service (speech, text, logic)  
- [ ] ROS 2 high-level integration  
- [ ] Visual configuration for devices  
- [ ] Remote classroom dashboard  
- [ ] Simplified installer and Docker container  
- [ ] AI-assisted robot design assistant
