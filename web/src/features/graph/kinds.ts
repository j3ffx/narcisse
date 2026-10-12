import type { EntityKind } from '@/lib/types';
import {
  AtSignIcon,
  Building2Icon,
  CircleUserRoundIcon,
  DropletIcon,
  FingerprintIcon,
  GlobeIcon,
  IdCardIcon,
  ImageIcon,
  LinkIcon,
  MailIcon,
  MapPinIcon,
  PhoneIcon,
  type LucideIcon,
} from 'lucide-react';
import { createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';

/** One pictogram per kind: in the graph, the list and the legend (never colour alone). */
export const KIND_ICONS: Record<EntityKind, LucideIcon> = {
  identity: FingerprintIcon,
  name: IdCardIcon,
  username: AtSignIcon,
  email: MailIcon,
  phone: PhoneIcon,
  address: MapPinIcon,
  domain: GlobeIcon,
  organization: Building2Icon,
  account: CircleUserRoundIcon,
  url: LinkIcon,
  leak: DropletIcon,
  photo: ImageIcon,
};

export type Theme = 'light' | 'dark';

/**
 * Node colours. Light theme: 700 shades, white pictograms; dark theme: 300 shades, dark
 * pictograms. Each fill stands out from the page (≥ 3:1) and its pictogram from the fill.
 */
export const KIND_COLORS: Record<Theme, Record<EntityKind, string>> = {
  light: {
    identity: '#374151',
    name: '#b45309',
    username: '#6d28d9',
    email: '#be123c',
    phone: '#0f766e',
    address: '#a16207',
    domain: '#1d4ed8',
    organization: '#4d7c0f',
    account: '#0369a1',
    url: '#475569',
    leak: '#b91c1c',
    photo: '#a21caf',
  },
  dark: {
    identity: '#e5e7eb',
    name: '#fcd34d',
    username: '#c4b5fd',
    email: '#fda4af',
    phone: '#5eead4',
    address: '#fde047',
    domain: '#93c5fd',
    organization: '#bef264',
    account: '#7dd3fc',
    url: '#cbd5e1',
    leak: '#fca5a5',
    photo: '#f0abfc',
  },
};

/** What the canvas draws besides the nodes, per theme. */
export const STAGE_COLORS: Record<
  Theme,
  { pictogram: string; label: string; labelBackdrop: string; edge: string; highlight: string }
> = {
  light: {
    pictogram: '#ffffff',
    label: '#1c2a24',
    labelBackdrop: '#ffffff',
    edge: '#c9d0d6',
    highlight: '#1c2a24',
  },
  dark: {
    pictogram: '#111b16',
    label: '#eef0ea',
    labelBackdrop: '#1c2a24',
    edge: '#33403a',
    highlight: '#eef0ea',
  },
};

/** A pictogram as an SVG data URL. Drawn with React, outside any render: flushSync only works
 * there (inside an effect it silently draws nothing). */
function draw(kind: EntityKind): string {
  const host = document.createElement('div');
  const root = createRoot(host);
  flushSync(() =>
    root.render(createElement(KIND_ICONS[kind], { size: 64, strokeWidth: 2.25, color: '#000' })),
  );
  const svg = host.innerHTML;
  root.unmount();
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

// Drawn once, when the graph's code loads.
const PICTOGRAMS = Object.fromEntries(
  (Object.keys(KIND_ICONS) as EntityKind[]).map((kind) => [kind, draw(kind)]),
) as Record<EntityKind, string>;

/** A kind's pictogram, for the canvas. */
export const pictogram = (kind: EntityKind): string => PICTOGRAMS[kind];
