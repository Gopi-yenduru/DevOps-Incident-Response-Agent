import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api/client';
import clsx from 'clsx';

export default function AccuracyFeedback({ incidentId, initialRating }) {
  const [rating, setRating] = useState(initialRating || 'unrated');
  const [loading, setLoading] = useState(false);

  const handleRate = async (newRating) => {
    if (rating === newRating) return;
    try {
      setLoading(true);
      await api.rateFix(incidentId, newRating);
      setRating(newRating);
    } catch (err) {
      console.error('Failed to rate incident', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-3 bg-slate-800/50 p-2 rounded-lg border border-devops-border">
      <span className="text-sm text-slate-300">Rate Agent Accuracy:</span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => handleRate('correct')}
          disabled={loading}
          className={clsx(
            "p-1.5 rounded hover:bg-slate-700 transition-colors disabled:opacity-50",
            rating === 'correct' ? "text-green-400 bg-slate-700" : "text-slate-400"
          )}
          title="Agent diagnosis and fix were correct"
        >
          <ThumbsUp className="h-4 w-4" />
        </button>
        <button
          onClick={() => handleRate('incorrect')}
          disabled={loading}
          className={clsx(
            "p-1.5 rounded hover:bg-slate-700 transition-colors disabled:opacity-50",
            rating === 'incorrect' ? "text-red-400 bg-slate-700" : "text-slate-400"
          )}
          title="Agent diagnosis or fix were incorrect"
        >
          <ThumbsDown className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
