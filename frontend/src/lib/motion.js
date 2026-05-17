const EASE_OUT = [0.22, 1, 0.36, 1];
const EASE_SOFT = [0.32, 0.72, 0, 1];

const DURATIONS = {
  instant: 0.08,
  fast: 0.3,
  base: 0.46,
  slow: 0.58,
};

export const LAYOUT_TRANSITION = {
  type: 'spring',
  stiffness: 360,
  damping: 34,
  mass: 0.82,
};

function getDuration(reduced, key) {
  return reduced ? DURATIONS.instant : DURATIONS[key];
}

export function getFadeTransition(reduced, key = 'base') {
  return {
    duration: getDuration(reduced, key),
    ease: EASE_OUT,
  };
}

export function getPagePresence(reduced, distance = 24) {
  return {
    initial: {
      opacity: 0,
      y: reduced ? 0 : distance,
    },
    animate: {
      opacity: 1,
      y: 0,
      transition: reduced
        ? getFadeTransition(true, 'fast')
        : {
            opacity: {
              duration: DURATIONS.slow,
              ease: EASE_OUT,
            },
            y: {
              duration: DURATIONS.base,
              ease: EASE_OUT,
            },
          },
    },
    exit: {
      opacity: 0,
      y: reduced ? 0 : 10,
      transition: {
        duration: getDuration(reduced, 'fast'),
        ease: EASE_SOFT,
      },
    },
  };
}

export function getSwapPresence(reduced, distance = 18) {
  return {
    initial: {
      opacity: 0,
      y: reduced ? 0 : distance,
    },
    animate: {
      opacity: 1,
      y: 0,
      transition: reduced
        ? getFadeTransition(true, 'fast')
        : {
            opacity: {
              duration: DURATIONS.base,
              ease: EASE_OUT,
            },
            y: {
              duration: DURATIONS.fast,
              ease: EASE_OUT,
            },
          },
    },
    exit: {
      opacity: 0,
      y: reduced ? 0 : 10,
      transition: {
        duration: getDuration(reduced, 'fast'),
        ease: EASE_SOFT,
      },
    },
  };
}

export function getItemPresence(reduced, distance = 16, scale = 0.965) {
  return {
    initial: {
      opacity: 0,
      y: reduced ? 0 : distance,
      scale: reduced ? 1 : scale,
    },
    animate: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: reduced
        ? getFadeTransition(true, 'fast')
        : {
            opacity: {
              duration: DURATIONS.base,
              ease: EASE_OUT,
            },
            y: {
              duration: DURATIONS.fast,
              ease: EASE_OUT,
            },
            scale: {
              duration: DURATIONS.fast,
              ease: EASE_OUT,
            },
          },
    },
    exit: {
      opacity: 0,
      y: reduced ? 0 : Math.min(distance, 6),
      scale: reduced ? 1 : 0.985,
      transition: {
        duration: getDuration(reduced, 'fast'),
        ease: EASE_SOFT,
      },
    },
  };
}

export function getModalOverlayPresence(reduced) {
  return {
    initial: { opacity: 0 },
    animate: {
      opacity: 1,
      transition: reduced
        ? getFadeTransition(true, 'fast')
        : {
            duration: DURATIONS.slow,
            ease: EASE_OUT,
          },
    },
    exit: {
      opacity: 0,
      transition: {
        duration: getDuration(reduced, 'fast'),
        ease: EASE_SOFT,
      },
    },
  };
}

export function getModalCardPresence(reduced) {
  return {
    initial: {
      opacity: 0,
      y: reduced ? 0 : 28,
      scale: reduced ? 1 : 0.94,
    },
    animate: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: reduced
        ? getFadeTransition(true, 'fast')
        : {
            opacity: {
              duration: DURATIONS.base,
              ease: EASE_OUT,
            },
            y: {
              type: 'spring',
              stiffness: 170,
              damping: 18,
              mass: 1,
            },
            scale: {
              type: 'spring',
              stiffness: 170,
              damping: 18,
              mass: 1,
            },
          },
    },
    exit: {
      opacity: 0,
      y: reduced ? 0 : 14,
      scale: reduced ? 1 : 0.97,
      transition: {
        duration: getDuration(reduced, 'fast'),
        ease: EASE_SOFT,
      },
    },
  };
}
