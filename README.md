
# AI-UX

> **Revolutionizing design validation with AI-powered user experience insights — before writing a single line of code.**

---

## 🚀 Project Description

AI-UX Tester is an intelligent, modular platform designed to empower designers and product teams with **real-time, data-driven UX insights** and **automated design iteration** workflows. It bridges the gap between static designs and real user behavior by leveraging cutting-edge AI models and Figma integration.

Built over 3 intense days for a hackathon, AI-UX Tester consists of **three powerful modules**:


| Module           | Key Capabilities                                                                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------- |
| UX Analysis      | Heatmaps, finger reach zones, drop-off identification, positive design points, UX scoring, AI suggestions |
| User Journey     | AI-driven simulation of user task completion and creation of screen-recorded walkthrough videos           |
| Design Iteration | AI-powered image generation to create improved design frames based on UX feedback and iteration needs     |

* Supports Figma file import via **Project ID, Design URL, or direct .fig upload**
* Prompt fields for each module allow user-guided AI customization
* Interactive heatmap visualizations with markers and tooltips
* Loading states with progressive text updates
* UX reports in rich text format for detailed review

---

## 🎯 Why AI-UX Tester?

Traditional UX testing is costly, slow, and happens too late—after development has begun. Our solution brings AI into the design phase itself, offering:

* **Instant UX feedback** from complex Figma files
* **Actionable, data-driven suggestions** for improvement
* **Automated generation of interactive user journey videos**
* **Seamless AI-driven design enhancement**

---

## 🛠️ Tech Stack

* **Backend:** Django REST Framework (Python 3.10)
* **Frontend:** HTML, CSS, jQuery, Heatmap.js, Font Awesome
* **AI:** OpenAI GPT-4o-mini (chat & vision), GEMINI
* **Integrations:** Figma REST & Image API

---

## 📸 Screenshots

![image](https://github.com/user-attachments/assets/56468bf4-6015-463e-9081-03305a86093f)


#### UX Analysis

![image](https://github.com/user-attachments/assets/e4418d7f-233c-483f-ac26-48a5499a2979)


#### User Journey

![image](https://github.com/user-attachments/assets/75a50934-eaeb-4c32-85c9-6889307052c1)


#### Design Iteration

![image](https://github.com/user-attachments/assets/199d5364-e92a-4575-b5dd-285d77eaf3f9)


---

## 🔧 Installation & Setup

```bash
git clone https://github.com/yourusername/ai-ux-tester.git
cd ai-ux-tester
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt

# Add your API keys and tokens in ai-ux views
OPENAI_API_KEY="your_openai_key"
FIGMA_ACCESS_TOKEN="your_figma_token"

# Run the server
python manage.py migrate
python manage.py runserver
```

---

## 🧪 How to Use

1. Select a Figma file by **project ID, design URL, or file upload**
2. You might also need Figma Access token so that system can acutally fetch the file for project ID and design URL.
3. Enter optional prompts to guide AI analysis
4. Run UX Analysis to get heatmaps, drop-offs, and UX scores
5. Generate a User Journey video to simulate task completion
6. Use Design Iteration to create AI-enhanced variants
7. Review reports, suggestions, and visualizations interactively

---

## ⚡ Future Roadmap (Coming Soon)

* Real-time collaborative UX design and feedback
* Persona-specific UX simulations (seniors, color-blind users, etc.)
* Accessibility auto-audit with WCAG compliance checks
* Multi-device and context-aware UX testing
* Enhanced data management with user history and versioning
* AR/VR immersive design testing
* Multiple flows/simulations detection in a single journey.

---

## 🤝 Contribution

Contributions, feedback, and ideas are welcome!
Please open issues or submit pull requests for improvements.

---
