import React from 'react';
import { motion } from 'framer-motion';

export default function AnimatedSection({ 
  children, 
  className = "", 
  delay = 0,
  staggerChildren = false,
  direction = "up"
}) {
  const variants = {
    hidden: { 
      opacity: 0, 
      y: direction === "up" ? 40 : direction === "down" ? -40 : 0,
      x: direction === "left" ? 40 : direction === "right" ? -40 : 0
    },
    visible: { 
      opacity: 1, 
      y: 0, 
      x: 0,
      transition: { 
        duration: 0.6, 
        ease: [0.22, 1, 0.36, 1],
        delay: delay,
        when: "beforeChildren",
        staggerChildren: staggerChildren ? 0.15 : 0
      }
    }
  };

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-100px" }}
      variants={variants}
      className={className}
    >
      {children}
    </motion.div>
  );
}
