import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import SwipeLeftimg from "../../../assets/gestures/swipeleft.png";

export default function SwipeLeft() {
  return (
    <GestureSandbox>
      {/* Current card */}
      <motion.div
        className="absolute inset-6 bg-hairline-strong rounded-md"
        animate={{ x: [0, -140] }}
        transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 0.5 }}
      />

      {/* Next card */}
      <motion.div
        className="absolute inset-6 bg-strong rounded-md"
        initial={{ x: 140 }}
        animate={{ x: [140, 0] }}
        transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 0.5 }}
      />

      {/* Hand */}
      <motion.img
        src={SwipeLeftimg}
        className="absolute bottom-2 right-2 h-40"
        animate={{ x: [20, -20] }}
        transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 0.5 }}
      />
    </GestureSandbox>
  );
}
