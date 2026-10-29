import React from 'react';

export const SeatMapSkeleton: React.FC = () => {
  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-8 animate-pulse">
      {/* Banner Skeleton */}
      <div className="w-full h-40 bg-surface-card rounded-2xl mb-8 border border-surface-border" />

      {/* Two Column Layout Skeleton */}
      <div className="flex flex-col lg:flex-row gap-8 items-start">
        {/* Left Seat Map Column (~70%) */}
        <div className="w-full lg:w-[68%] bg-surface-card/50 border border-surface-border rounded-2xl p-8 flex flex-col items-center">
          <div className="w-3/4 h-8 bg-surface-hover rounded-full mb-12" />

          {/* Seat Grid Rows */}
          <div className="space-y-4 w-full flex flex-col items-center">
            {Array.from({ length: 8 }).map((_, rIdx) => (
              <div key={rIdx} className="flex space-x-3 items-center">
                <div className="w-4 h-4 bg-surface-hover rounded" />
                <div className="flex space-x-2">
                  {Array.from({ length: 14 }).map((_, cIdx) => (
                    <div
                      key={cIdx}
                      className="w-7 h-7 sm:w-8 sm:h-8 bg-surface-hover rounded-md"
                    />
                  ))}
                </div>
                <div className="w-4 h-4 bg-surface-hover rounded" />
              </div>
            ))}
          </div>
        </div>

        {/* Right Sticky Summary Skeleton (~30%) */}
        <div className="w-full lg:w-[32%] bg-surface-card border border-surface-border rounded-2xl p-6 space-y-4">
          <div className="h-6 bg-surface-hover rounded w-3/4" />
          <div className="h-4 bg-surface-hover rounded w-1/2" />
          <div className="h-20 bg-surface-hover rounded-xl my-4" />
          <div className="h-12 bg-blue-900/40 rounded-xl" />
        </div>
      </div>
    </div>
  );
};
