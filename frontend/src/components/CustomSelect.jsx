import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown } from 'lucide-react';
import styles from './CustomSelect.module.css';

export default function CustomSelect({ value, onChange, options, placeholder, compact }) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0, width: 0 });
  const triggerRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    function onDown(e) {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        listRef.current && !listRef.current.contains(e.target)
      ) setOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, []);

  function handleOpen() {
    if (!open && triggerRef.current) {
      const r = triggerRef.current.getBoundingClientRect();
      setCoords({ top: r.bottom + 4, left: r.left, width: r.width });
    }
    setOpen(o => !o);
  }

  const selected = options.find(o => o.value === value);

  return (
    <div className={`${styles.wrap} ${compact ? styles.compact : ''}`}>
      <button
        type="button"
        ref={triggerRef}
        className={`${styles.trigger} ${open ? styles.triggerOpen : ''}`}
        onClick={handleOpen}
      >
        <span className={selected ? styles.value : styles.placeholder}>
          {selected ? selected.label : (placeholder ?? 'Select')}
        </span>
        <ChevronDown size={13} className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`} />
      </button>

      {open && createPortal(
        <ul
          ref={listRef}
          className={styles.list}
          style={{ position: 'fixed', top: coords.top, left: coords.left, minWidth: coords.width }}
        >
          {options.map(o => (
            <li
              key={o.value}
              className={`${styles.option} ${value === o.value ? styles.optionActive : ''}`}
              onMouseDown={() => { onChange(o.value); setOpen(false); }}
            >
              {o.label}
            </li>
          ))}
        </ul>,
        document.body
      )}
    </div>
  );
}
