export default function Loading() {
  return (
    <div className="skel-root space-y-6" aria-busy="true" aria-label="Loading">
      <div className="skel h-7 w-44" />
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <div key={i} className="skel h-24" />)}</div>
      <div className="skel h-72" />
    </div>
  );
}
