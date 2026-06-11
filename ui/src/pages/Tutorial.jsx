import { useEffect, useState } from "react";
import {
  SwipeLeft,
  SwipeRight,
  CursorMove,
  LeftClick,
  RightClick,
  ScrollUp,
  ScrollDown,
  Screenshot,
} from "../components/gesture-tutorial";

const voiceExamples = [
  {
    title: "Open apps",
    phrases: ["open my browser", "start Spotify", "launch Visual Studio Code"],
    description: "Quickly open or switch to applications using natural speech.",
  },
  {
    title: "Control volume",
    phrases: ["mute the sound", "turn it down", "make it louder"],
    description: "Adjust system volume without touching the keyboard.",
  },
  {
    title: "Adjust display",
    phrases: ["increase brightness", "make the screen dimmer"],
    description: "Control screen brightness with simple voice commands.",
  },
  {
    title: "Navigate content",
    phrases: ["scroll down", "go to the top", "move to the bottom"],
    description: "Scroll through pages and documents hands-free.",
  },
  {
    title: "Open folders",
    phrases: ["open downloads", "show my pictures"],
    description: "Jump directly to common system folders.",
  },
];

const gestures = [
  { name: "Swipe Left", demo: <SwipeLeft /> },
  { name: "Swipe Right", demo: <SwipeRight /> },
  { name: "Move Cursor", demo: <CursorMove /> },
  { name: "Left Click", demo: <LeftClick /> },
  { name: "Right Click", demo: <RightClick /> },
  { name: "Scroll Up", demo: <ScrollUp /> },
  { name: "Scroll Down", demo: <ScrollDown /> },
  { name: "Screenshot", demo: <Screenshot /> },
];

export default function Tutorial() {
  return (
    <div className="h-full w-full overflow-y-auto px-6 py-6 space-y-6 bg-[#0d0b1e]/70">
      
      {/* HEADER */}
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-white">
          Getting Started
        </h1>
        <p className="text-sm text-violet-300 max-w-xl">
          Control your computer using voice and gestures. Speak naturally,
          move confidently, and let the assistant do the rest.
        </p>
      </header>

      {/* CORE CONCEPT */}
      <section className="grid gap-4 md:grid-cols-3">
        {[
          {
            title: "Speak naturally",
            text: "Use everyday language. You don’t need to remember exact commands.",
          },
          {
            title: "Use simple gestures",
            text: "Perform clear, deliberate movements within the camera view.",
          },
          {
            title: "Watch the feedback",
            text: "The dashboard shows what the assistant understands in real time.",
          },
        ].map((item) => (
          <div
            key={item.title}
            className="rounded-xl border border-[#2e2a5a] bg-[#13112b]/70 p-4"
          >
            <h3 className="text-sm font-semibold text-white">
              {item.title}
            </h3>
            <p className="text-sm text-violet-300 mt-1">{item.text}</p>
          </div>
        ))}
      </section>

      {/* GESTURES */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-white">
          Gesture controls
        </h2>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {gestures.map((g) => (
            <div
              key={g.name}
              className="rounded-xl border border-[#2e2a5a] bg-[#13112b]/70 p-3 space-y-2"
            >
              {g.demo}
              <div className="text-center text-xs font-medium text-violet-100">
                {g.name}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* VOICE */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-white">
          Voice examples
        </h2>

        <div className="grid gap-4 md:grid-cols-2">
          {voiceExamples.map((v) => (
            <div
              key={v.title}
              className="rounded-xl border border-[#2e2a5a] bg-[#13112b]/70 p-4 space-y-2"
            >
              <h3 className="text-sm font-semibold text-white">
                {v.title}
              </h3>

              <div className="flex flex-wrap gap-2">
                {v.phrases.map((p) => (
                  <span
                    key={p}
                    className="rounded-full bg-[#1e1b3a] px-3 py-1 text-xs text-violet-100"
                  >
                    “{p}”
                  </span>
                ))}
              </div>

              <p className="text-sm text-violet-300">{v.description}</p>
            </div>
          ))}
        </div>
      </section>

      
    </div>
  );
}

