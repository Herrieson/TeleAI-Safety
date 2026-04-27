"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

type TourStep = {
  target: string;
  title: string;
  description: string;
};

type NewRunTourProps = {
  open: boolean;
  steps: TourStep[];
  layoutKey?: string;
  labels: {
    title: string;
    step: string;
    previous: string;
    next: string;
    finish: string;
    skip: string;
  };
  onStepChange?: (index: number) => void;
  onClose: (completed: boolean) => void;
};

type SpotlightLayout = {
  targetRect: DOMRect;
  cardWidth: number;
  cardLeft: number;
  cardTop: number;
  lineLeft: number;
  lineTop: number;
  lineWidth: number;
  lineAngle: number;
};

const CARD_WIDTH = 340;
const CARD_HEIGHT = 220;
const VIEWPORT_GAP = 16;
const TARGET_GAP = 22;

export function NewRunTour({ open, steps, layoutKey, labels, onStepChange, onClose }: NewRunTourProps) {
  const [activeStep, setActiveStep] = useState(0);
  const [layout, setLayout] = useState<SpotlightLayout | null>(null);
  const [mounted, setMounted] = useState(false);

  const step = steps[activeStep] || null;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (open) {
      setActiveStep(0);
    }
  }, [open]);

  useEffect(() => {
    if (open) {
      onStepChange?.(activeStep);
    }
  }, [activeStep, onStepChange, open]);

  useEffect(() => {
    if (!open || !step) {
      setLayout(null);
      return;
    }

    const target = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
    target?.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
  }, [layoutKey, open, step]);

  useEffect(() => {
    if (!open || !step) {
      setLayout(null);
      return;
    }

    let frameId = 0;

    const updateLayout = () => {
      const target = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      if (!target) {
        setLayout(null);
        return;
      }

      frameId = window.requestAnimationFrame(() => {
        const rect = target.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const cardWidth = Math.min(CARD_WIDTH, Math.max(280, viewportWidth - VIEWPORT_GAP * 2));
        const placeAbove = rect.bottom + CARD_HEIGHT + TARGET_GAP + VIEWPORT_GAP > viewportHeight && rect.top > CARD_HEIGHT + TARGET_GAP;
        const cardTopBase = placeAbove ? rect.top - CARD_HEIGHT - TARGET_GAP : rect.bottom + TARGET_GAP;
        const cardLeft = clamp(rect.left + rect.width / 2 - cardWidth / 2, VIEWPORT_GAP, viewportWidth - cardWidth - VIEWPORT_GAP);
        const cardTop = clamp(cardTopBase, VIEWPORT_GAP, viewportHeight - CARD_HEIGHT - VIEWPORT_GAP);
        const targetX = rect.left + rect.width / 2;
        const targetY = placeAbove ? rect.top : rect.bottom;
        const cardX = clamp(targetX, cardLeft + 36, cardLeft + cardWidth - 36);
        const cardY = placeAbove ? cardTop + CARD_HEIGHT : cardTop;
        const deltaX = targetX - cardX;
        const deltaY = targetY - cardY;
        const lineWidth = Math.max(0, Math.sqrt(deltaX ** 2 + deltaY ** 2) - 12);
        const lineAngle = (Math.atan2(deltaY, deltaX) * 180) / Math.PI;

        setLayout({
          targetRect: rect,
          cardWidth,
          cardLeft,
          cardTop,
          lineLeft: cardX,
          lineTop: cardY,
          lineWidth,
          lineAngle
        });
      });
    };

    updateLayout();

    const handleChange = () => updateLayout();
    window.addEventListener("resize", handleChange);
    window.addEventListener("scroll", handleChange, true);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", handleChange);
      window.removeEventListener("scroll", handleChange, true);
    };
  }, [layoutKey, open, step]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose(false);
      } else if (event.key === "ArrowRight" && activeStep < steps.length - 1) {
        setActiveStep((prev) => prev + 1);
      } else if (event.key === "ArrowLeft" && activeStep > 0) {
        setActiveStep((prev) => prev - 1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeStep, onClose, open, steps.length]);

  const progressLabel = useMemo(() => `${activeStep + 1} / ${steps.length}`, [activeStep, steps.length]);

  if (!mounted || !open || !step || !layout) {
    return null;
  }

  return createPortal(
    <div aria-live="polite" aria-modal="true" className="tour-overlay" role="dialog">
      <button aria-label={labels.skip} className="tour-backdrop" onClick={() => onClose(false)} type="button" />
      <div
        className="tour-spotlight"
        style={{
          top: `${layout.targetRect.top - 8}px`,
          left: `${layout.targetRect.left - 8}px`,
          width: `${layout.targetRect.width + 16}px`,
          height: `${layout.targetRect.height + 16}px`
        }}
      />
      <div
        aria-hidden="true"
        className="tour-arrow"
        style={{
          left: `${layout.lineLeft}px`,
          top: `${layout.lineTop}px`,
          width: `${layout.lineWidth}px`,
          transform: `rotate(${layout.lineAngle}deg)`
        }}
      />
      <section
        className="tour-card"
        style={{
          left: `${layout.cardLeft}px`,
          top: `${layout.cardTop}px`,
          width: `${layout.cardWidth}px`
        }}
      >
        <p className="tour-kicker">
          {labels.title}
          <span>
            {labels.step} {progressLabel}
          </span>
        </p>
        <h3 className="tour-heading">{step.title}</h3>
        <p className="tour-copy">{step.description}</p>
        <div className="tour-actions">
          <button className="btn" onClick={() => onClose(false)} type="button">
            {labels.skip}
          </button>
          <div className="tour-actions-right">
            <button className="btn" disabled={activeStep === 0} onClick={() => setActiveStep((prev) => Math.max(0, prev - 1))} type="button">
              {labels.previous}
            </button>
            <button
              className="btn btn-primary"
              onClick={() => {
                if (activeStep === steps.length - 1) {
                  onClose(true);
                  return;
                }
                setActiveStep((prev) => Math.min(steps.length - 1, prev + 1));
              }}
              type="button"
            >
              {activeStep === steps.length - 1 ? labels.finish : labels.next}
            </button>
          </div>
        </div>
      </section>
    </div>,
    document.body
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
