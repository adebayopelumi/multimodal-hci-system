import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import Screenshotimg from "../../../assets/gestures/screenshot.png";

export default function Screenshot() {
  return (
    <GestureSandbox>
      <div className="absolute inset-6 bg-strong rounded-md" />

      <motion.div
        className="absolute inset-0 bg-white"
        animate={{ opacity: [0, 0.8, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
      />

      <motion.div
        className="absolute inset-6 border-2 border-ink"
        animate={{ scale: [1, 0.95, 1] }}
        transition={{ duration: 2, repeat: Infinity }}
      />

      <motion.img
        src={Screenshotimg}
        className="absolute bottom-2 right-2 h-40 mr-2"
        animate={{
          scale: [1, 0.95, 1],
        }}
        transition={{
          duration: 1.3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </GestureSandbox>
  );
}
