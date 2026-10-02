export function isOnboardingEnabled(): boolean {
  return window.sprkeyDesktop?.guestOnboardingEnabled === true
}
