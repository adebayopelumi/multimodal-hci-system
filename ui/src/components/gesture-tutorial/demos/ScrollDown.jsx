import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import ScrollDownimg from "../../../assets/gestures/scrolldown.png";

export default function ScrollDown() {
  return (
    <GestureSandbox>
      <motion.div
        className="absolute inset-x-4 top-4 space-y-2"
        initial={{ y: 0 }}
        animate={{ y: 150 }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: "linear",
        }}
      >
        <div className="h-4 bg-slate-300 rounded" />
        <div className="h-4 bg-slate-300 rounded" />
        <div className="h-4 bg-slate-300 rounded" />
        <div className="h-4 bg-slate-300 rounded" />
      </motion.div>

      <motion.img
        src={ScrollDownimg}
        className="absolute bottom-2 right-2 h-40"
        animate={{
          y: [0, -2, 0],
          scale: [1, 0.98, 1],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </GestureSandbox>
  );
}
