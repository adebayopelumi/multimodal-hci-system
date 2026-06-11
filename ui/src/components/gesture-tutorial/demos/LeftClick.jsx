import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import leftClickimg from "../../../assets/gestures/leftclick.png";

export default function LeftClick() {
  return (
    <GestureSandbox>
      <motion.div
        className="absolute w-3 h-3 bg-black rounded-full"
        animate={{ x: 80, y: 60 }}
      />

      <motion.div
        className="absolute w-10 h-10 border border-black rounded-full"
        animate={{ scale: [0, 1, 0], opacity: [0, 1, 0] }}
        transition={{ duration: 1.5, repeat: Infinity }}
        style={{ left: 74, top: 54 }}
      />

      <motion.img
        src={leftClickimg}
        className="absolute bottom-2 right-2 h-32 mr-12"
        animate={{ scale: [1, 0.96, 1] }}
        transition={{
          duration: 1.4,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </GestureSandbox>
  );
}
