import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import ScrollUpimg from "../../../assets/gestures/scrollup.png";

export default function ScrollUp() {
  return (
    <GestureSandbox>
      <motion.div
        className="absolute inset-x-4 top-20 space-y-2"
        initial={{ y: 100 }}
        animate={{ y: -50 }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: "linear",
        }}
      >
        <div className="h-4 bg-hairline-strong rounded" />
        <div className="h-4 bg-hairline-strong rounded" />
        <div className="h-4 bg-hairline-strong rounded" />
        <div className="h-4 bg-hairline-strong rounded" />
      </motion.div>

      <motion.img
        src={ScrollUpimg}
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
