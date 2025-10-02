import { render, screen } from '@testing-library/react';
import App from './App';

test('renders a single Hello heading', () => {
  render(<App />);
  const headings = screen.getAllByRole('heading', { name: /hello, world/i });
  expect(headings).toHaveLength(1);
});
