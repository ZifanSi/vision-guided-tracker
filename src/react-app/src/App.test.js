import { render, screen } from '@testing-library/react';
import App from './App';

test('renders Hello, world', () => {
  render(<App />);
  expect(screen.getByText(/hello/i)).toBeInTheDocument();
});
