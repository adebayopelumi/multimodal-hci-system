import { motion } from "framer-motion";
import GestureSandbox from "../GestureSandbox";
import cursorMoveImg from "../../../assets/gestures/cursormove.png";

export default function CursorMove() {
  return (
    <GestureSandbox>
      <div className="relative w-full h-full flex items-center justify-center">

        {/* Cursor dot — close to hand */}
        <motion.div
          className="absolute z-20 w-2.5 h-2.5 bg-ink rounded-full"
          animate={{
            x: [-55, -35, -45, -55], // MUCH closer
            y: [0, 10, 18, 0],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />

        {/* Hand gesture */}
        <motion.img
          src={cursorMoveImg}
          className="absolute z-10 h-40 mb-6"
          animate={{
            x: [0, 22, 12, 0],
            y: [0, 15, 22, 0],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />

      </div>
    </GestureSandbox>
  );
}
