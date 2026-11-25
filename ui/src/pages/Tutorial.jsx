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
import { Card, Eyebrow, Page, PageHeader } from "../components/ui";

const steps = [
  {
    title: "Start the assistant",
    text: "On the Dashboard, pick Voice, Gesture or both, then press Start.",
  },
  {
    title: "Say “Hey Jarvis”",
    text: "Wait for the chime, then ask in one sentence. You can chain several steps with “and”.",
  },
  {
    title: "Or use your hand",
    text: "Keep your hand in view of the camera. The Dashboard shows each gesture it recognises.",
  },
];

const voiceExamples = [
  {
    title: "Apps & websites",
    phrases: ["open Spotify", "open YouTube", "close Safari"],
  },
  {
    title: "Several steps at once",
    phrases: ["open YouTube and play the latest MrBeast video", "open Spotify and play Wizkid"],
  },
  {
    title: "Questions & search",
    phrases: ["what's the tallest building in the world?", "find restaurants near me"],
  },
  {
    title: "Messages & notes",
    phrases: ["message Mum on WhatsApp saying I'm on my way", "make a note to buy milk and eggs"],
    note: "Messages and emails are only drafted. You press send.",
  },
  {
    title: "Your Mac",
    phrases: ["turn the volume down", "what time is it?", "open my downloads"],
  },
];

const gestures = [
  { name: "Swipe left", demo: <SwipeLeft /> },
  { name: "Swipe right", demo: <SwipeRight /> },
  { name: "Move cursor", demo: <CursorMove /> },
  { name: "Left click", demo: <LeftClick /> },
  { name: "Right click", demo: <RightClick /> },
  { name: "Scroll up", demo: <ScrollUp /> },
  { name: "Scroll down", demo: <ScrollDown /> },
  { name: "Screenshot", demo: <Screenshot /> },
];

export default function Tutorial() {
  return (
    <Page className="space-y-12">
      <PageHeader
        eyebrow="Help"
        title="Getting started"
        description="Control your Mac with your voice and your hands. Speak naturally; you don't need exact commands."
      />

      {/* How it works */}
      <ol className="grid gap-4 md:grid-cols-3">
        {steps.map((step, i) => (
          <li key={step.title}>
            <Card className="h-full p-5">
              <span className="font-mono text-caption text-muted">{String(i + 1).padStart(2, "0")}</span>
              <h3 className="mt-3 text-title font-semibold text-ink">{step.title}</h3>
              <p className="mt-1 text-ui text-body">{step.text}</p>
            </Card>
          </li>
        ))}
      </ol>

      {/* Voice */}
      <section className="space-y-4">
        <div>
          <Eyebrow>Voice</Eyebrow>
          <h2 className="mt-2 text-display-sm font-normal text-ink">Things you can say</h2>
        </div>

        <Card className="divide-y divide-hairline-soft">
          {voiceExamples.map((group) => (
            <div key={group.title} className="grid gap-3 px-5 py-4 md:grid-cols-[200px_1fr] md:items-baseline">
              <h3 className="text-ui font-medium text-ink">{group.title}</h3>
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2">
                  {group.phrases.map((p) => (
                    <code
                      key={p}
                      className="rounded-sm border border-hairline bg-canvas-soft px-2 py-1 font-mono text-[12px] text-ink"
                    >
                      “{p}”
                    </code>
                  ))}
                </div>
                {group.note && <p className="text-caption text-muted">{group.note}</p>}
              </div>
            </div>
          ))}
        </Card>
      </section>

      {/* Gestures */}
      <section className="space-y-4">
        <div>
          <Eyebrow>Gestures</Eyebrow>
          <h2 className="mt-2 text-display-sm font-normal text-ink">Hand controls</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {gestures.map((g) => (
            <Card key={g.name} className="overflow-hidden">
              {g.demo}
              <p className="border-t border-hairline-soft px-4 py-3 text-ui font-medium text-ink">{g.name}</p>
            </Card>
          ))}
        </div>
      </section>
    </Page>
  );
}
