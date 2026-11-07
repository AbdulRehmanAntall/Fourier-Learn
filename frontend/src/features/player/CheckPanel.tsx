"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

import { MathText } from "@/components/MathText";
import type { Schemas } from "@/lib/api/client";
import { answerCheck } from "@/lib/api/hooks/player";

// The check after a module (docs/frontend.md §6.8, Fig. 4.4, UC 4.6): one question at a time,
// and one tap answers. Whether the answer is right comes only from the server (rule 1). The
// check never blocks the lesson: a wrong answer continues, and if the answer can't be sent the
// panel moves on at once while the request is retried in the background, with no result to show.

const RESULT_MS = 1500;

type Item = Schemas["CheckItem"];
type Result = Schemas["CheckResponseResult"];

export function CheckPanel({
  moduleId,
  items,
  onDone,
}: {
  moduleId: number;
  items: Item[];
  onDone(): void;
}) {
  const [index, setIndex] = useState(0);

  return (
    <section className="flex flex-col gap-5 rounded-lg border border-current/15 p-6">
      <div>
        <h2 className="text-xl font-semibold">Quick check before we continue</h2>
        {items.length > 1 && (
          <p className="mt-1 text-sm opacity-70">
            Question {index + 1} of {items.length}
          </p>
        )}
      </div>
      <Question
        key={items[index].id}
        moduleId={moduleId}
        item={items[index]}
        onNext={() => (index + 1 < items.length ? setIndex(index + 1) : onDone())}
      />
      <p className="text-sm opacity-70">
        Your answer updates your confidence profile and the difficulty of upcoming modules.
      </p>
    </section>
  );
}

function Question({ moduleId, item, onNext }: { moduleId: number; item: Item; onNext(): void }) {
  const question = useRef<HTMLParagraphElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  // Kept as state, not a direct onNext() in the promise: if the student has already pressed
  // Continue, this component is gone, and a late failure must not skip the next question.
  const [failed, setFailed] = useState(false);
  const next = useEffectEvent(onNext);

  // Each new question takes the focus, so keyboard and screen-reader users land on it.
  useEffect(() => question.current?.focus(), []);

  useEffect(() => {
    if (!result && !failed) return;
    const timer = setTimeout(() => next(), failed ? 0 : RESULT_MS);
    return () => clearTimeout(timer);
  }, [result, failed]);

  function answer(option: string) {
    setSelected(option);
    answerCheck({ module_id: moduleId, check_id: item.id, selected_option: option }).then(
      setResult,
      () => setFailed(true),
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p ref={question} tabIndex={-1} className="text-lg outline-none">
        <MathText text={item.question_text} />
      </p>

      <div className={`grid gap-3 ${item.item_type === "true_false" ? "grid-cols-2" : ""}`}>
        {item.options.map((option) => (
          <button
            key={option}
            type="button"
            disabled={selected !== null}
            onClick={() => answer(option)}
            className={`min-h-11 rounded-lg border-2 px-4 py-2 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 ${
              item.item_type === "true_false" ? "text-center" : "text-left"
            } ${optionStyle(option, selected, result)}`}
          >
            {result?.correct_option === option && <span aria-hidden>✓ </span>}
            {result && selected === option && !result.is_correct && <span aria-hidden>✗ </span>}
            <MathText text={option} />
          </button>
        ))}
      </div>

      <div className="flex min-h-11 flex-wrap items-center justify-between gap-3">
        <p role="status" className="font-semibold">
          {result &&
            (result.is_correct ? (
              <span className="text-green-700 dark:text-green-400">Correct!</span>
            ) : (
              <span>
                Not quite. The answer is <MathText text={result.correct_option} />.
              </span>
            ))}
        </p>
        {selected !== null && (
          <button
            type="button"
            // The tapped option is now disabled and has lost the focus, so bring it here.
            autoFocus
            onClick={onNext}
            className="h-11 rounded-full bg-blue-600 px-6 font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            Continue
          </button>
        )}
      </div>
    </div>
  );
}

function optionStyle(option: string, selected: string | null, result: Result | null) {
  if (result?.correct_option === option) {
    return "border-green-600 bg-green-600/10";
  }
  if (selected === option) {
    return result ? "border-red-600 bg-red-600/10" : "border-blue-600 bg-blue-600/10";
  }
  return selected === null
    ? "border-current/25 hover:bg-current/10"
    : "border-current/15 opacity-60";
}
