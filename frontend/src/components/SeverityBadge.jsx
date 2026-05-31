import clsx from 'clsx';

export default function SeverityBadge({ severity }) {
  const styles = {
    critical: "bg-red-500/10 text-red-400 border-red-500/20",
    error: "bg-orange-500/10 text-orange-400 border-orange-500/20",
    warning: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    normal: "bg-green-500/10 text-green-400 border-green-500/20",
  };

  const currentStyle = styles[severity?.toLowerCase()] || styles.normal;

  return (
    <span className={clsx("px-2.5 py-0.5 rounded-full text-xs font-semibold border uppercase tracking-wide", currentStyle)}>
      {severity}
    </span>
  );
}
