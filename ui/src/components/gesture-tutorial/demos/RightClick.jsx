import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import RightClickimg from "../../../assets/gestures/rightclick.png";

export default function RightClick() {
  return (
    <GestureSandbox>
      <motion.div
        className="absolute w-3 h-3 bg-black rounded-full"
        style={{ left: 80, top: 60 }}
      />

      <motion.div
        className="absolute text-xs bg-[#1e1b3a] text-white px-2 py-1 rounded"
        animate={{ opacity: [0, 1, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
        style={{ left: 90, top: 70 }}
      >
        Menu
      </motion.div>

      <motion.img
        src={RightClickimg}
        className="absolute bottom-2 right-2 h-32 mr-12"
        animate={{
          scale: [1, 0.97, 1],
          y: [0, -1, 0],
        }}
        transition={{
          duration: 1.8,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
    </GestureSandbox>
  );
}
