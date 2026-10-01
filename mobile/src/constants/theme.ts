/**
 * Below are the colors that are used in the app. The colors are defined in the light and dark mode.
 * There are many other ways to style your app. For example, [Nativewind](https://www.nativewind.dev/), [Tamagui](https://tamagui.dev/), [unistyles](https://reactnativeunistyles.vercel.app), etc.
 */

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#000000',
    background: '#ffffff',
    backgroundElement: '#F0F0F3',
    backgroundSelected: '#E0E1E6',
    textSecondary: '#60646C',
    border: '#D9DBE0',
    accent: '#2563EB',
    onAccent: '#FFFFFF',
    danger: '#DC2626',
    success: '#15803D',
    warning: '#B45309',
    warningBackground: '#FEF3C7',
  },
  dark: {
    text: '#ffffff',
    background: '#000000',
    backgroundElement: '#212225',
    backgroundSelected: '#2E3135',
    textSecondary: '#B0B4BA',
    border: '#34373C',
    accent: '#60A5FA',
    onAccent: '#0B1220',
    danger: '#F87171',
    success: '#4ADE80',
    warning: '#FBBF24',
    warningBackground: '#3A2E12',
  },
} as const;

// The web app's fixed workout palette (training.models.COLOR_CHOICES).
export const WorkoutColors = {
  light: {
    red: '#DC2626',
    blue: '#2563EB',
    green: '#16A34A',
    amber: '#D97706',
    violet: '#7C3AED',
    teal: '#0D9488',
    rose: '#E11D48',
  },
  dark: {
    red: '#F87171',
    blue: '#60A5FA',
    green: '#4ADE80',
    amber: '#FBBF24',
    violet: '#A78BFA',
    teal: '#2DD4BF',
    rose: '#FB7185',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;
