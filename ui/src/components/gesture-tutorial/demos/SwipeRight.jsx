import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import SwipeRightimg from "../../../assets/gestures/swiperight.png";

export default function SwipeRight() {
  return (
    <GestureSandbox>
      {/* Current card */}
      <motion.div
        className="absolute inset-6 bg-slate-300 rounded-md"
        animate={{ x: [0, 140] }}
        transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 0.5 }}
      />

      {/* Next card */}
      <motion.div
        className="absolute inset-6 bg-slate-200 rounded-md"
        initial={{ x: -140 }}
        animate={{ x: [-140, 0] }}
        transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 0.5 }}
      />

      {/* Hand */}
      <motion.img
        src={SwipeRightimg}
        className="absolute bottom-2 left-2 h-40"
        animate={{ x: [-20, 20] }}
        transition={{ duration: 1.5, repeat: Infinity, repeatDelay: 0.5 }}
      />
    </GestureSandbox>
  );
}
