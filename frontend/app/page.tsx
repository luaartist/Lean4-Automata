import { redirect } from 'next/navigation';

// Landing page redirects to first project (project_id=1 by default)
export default function HomePage() {
  redirect('/projects/1');
}
