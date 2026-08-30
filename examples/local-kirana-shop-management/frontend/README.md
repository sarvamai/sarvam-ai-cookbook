# VendorVoice Frontend Dashboard

The frontend for VendorVoice is a highly responsive, modern web application built with **Next.js** and **React**. It features a mobile-first yet desktop-optimized design (glassmorphism aesthetic) and fully supports internationalization for 11 different languages.

## 🛠️ Technology Stack
- **Framework:** Next.js (React)
- **Styling:** Tailwind CSS
- **Icons:** Lucide React

## 🌟 Key Features
- **Responsive Dashboard Grid:** A smooth grid system that adapts to mobile devices, tablets, and large displays.
- **Multilingual Support:** The entire UI toggles dynamically between 11 languages via a built-in translation dictionary.
- **Microphone UI:** A sleek floating action button that captures audio streams using the browser's MediaRecorder API.
- **Advanced Search & Filtering:** Users can filter their history by Name, Month, and Year natively within the client.

## ⚙️ Environment Variables
Create a `.env.local` file in this `frontend` directory with the following variable to point to the backend server:

```ini
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```
*(Next.js will use this variable to avoid hardcoding API paths inside the application.)*

## 🚀 Setup & Running

1. **Install Dependencies:**
   Make sure you have Node.js installed, then run:
   ```bash
   npm install
   ```

2. **Start the Development Server:**
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser to view the application.

## 📁 Key Files
- `src/app/page.tsx`: The main React component that handles the recording logic, UI translation map, history states, and the responsive grid rendering.
- `src/app/layout.tsx`: The root layout defining font families and global HTML wrapping.
