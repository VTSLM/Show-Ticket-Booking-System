import React from 'react';
import { MapPin, Film, Clock, Calendar } from 'lucide-react';
import { ShowDetails } from '../types/seat';
import { formatShowDateTime, formatDuration } from '../utils/formatters';

interface ShowBannerProps {
  show: ShowDetails;
  reconnecting?: boolean;
}

export const ShowBanner: React.FC<ShowBannerProps> = ({ show, reconnecting }) => {
  const { fullStr } = formatShowDateTime(show.start_time);
  const durationText = formatDuration(show.duration);

  return (
    <div className="relative w-full overflow-hidden rounded-2xl bg-surface-card border border-surface-border mb-8 shadow-xl">
      {/* Blurred Backdrop of Poster Image */}
      {show.poster_url && (
        <div
          className="absolute inset-0 bg-cover bg-center filter blur-3xl opacity-20 scale-125 transform pointer-events-none"
          style={{ backgroundImage: `url(${show.poster_url})` }}
        />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-surface-card via-surface-card/85 to-transparent pointer-events-none" />

      {/* Main Content Content Row */}
      <div className="relative p-6 sm:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-md">
              {show.language}
            </span>
            <span className="px-2.5 py-0.5 text-xs font-medium bg-gray-800 text-gray-300 border border-gray-700 rounded-md">
              {show.genre}
            </span>
            <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-xs font-medium bg-gray-800 text-gray-300 border border-gray-700 rounded-md">
              <Clock className="w-3 h-3 text-gray-400" />
              <span>{durationText}</span>
            </span>
            {reconnecting && (
              <span className="px-2.5 py-0.5 text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded-md animate-pulse">
                Reconnecting...
              </span>
            )}
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight drop-shadow">
            {show.title}
          </h1>

          <div className="flex flex-wrap items-center gap-y-2 gap-x-6 text-sm text-gray-300">
            <div className="flex items-center space-x-1.5">
              <MapPin className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span>
                <span className="font-semibold text-white">{show.venue}</span> ({show.city})
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Film className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span className="text-gray-300">{show.screen}</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Calendar className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span className="text-gray-200 font-medium">{fullStr}</span>
            </div>
          </div>
        </div>

        {/* Thumbnail preview if available */}
        {show.poster_url && (
          <div className="hidden lg:block w-20 h-28 rounded-lg overflow-hidden border border-gray-700 shadow-md flex-shrink-0">
            <img
              src={show.poster_url}
              alt={show.title}
              className="w-full h-full object-cover"
            />
          </div>
        )}
      </div>
    </div>
  );
};
