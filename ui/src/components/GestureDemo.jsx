import { motion } from "framer-motion";

export default function GestureDemo({ src, type }) {
  const animations = {
    swipeLeft: {
      animate: { x: [-40, 40, -40] },
      transition: { duration: 5, repeat: Infinity, ease: "easeInOut" },
    },
    swipeRight: {
      animate: { x: [40, -40, 40] },
      transition: { duration: 5, repeat: Infinity, ease: "easeInOut" },
    },
    scrollUp: {
      animate: { y: [20, -20, 20] },
      transition: { duration: 2, repeat: Infinity },
    },
    scrollDown: {
      animate: { y: [-20, 20, -20] },
      transition: { duration: 2, repeat: Infinity },
    },
    click: {
      animate: { scale: [1, 0.9, 1] },
      transition: { duration: 1.2, repeat: Infinity },
    },
    static: {
      animate: { scale: [1, 1.05, 1] },
      transition: { duration: 2.5, repeat: Infinity },
    },
  };

  return (
    <div className="flex items-center justify-center bg-canvas-soft rounded-lg h-40 border border-hairline">
      <motion.img
        src={src}
        alt=""
        className="h-28 object-contain"
        {...animations[type]}
      />
    </div>
  );
}
