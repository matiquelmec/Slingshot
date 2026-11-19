import { redirect } from 'next/navigation';
import { isFtmoMt5Visible } from '@/shared';
import FtmoTerminalView from './FtmoTerminalView';

export default function FtmoPage() {
    if (!isFtmoMt5Visible()) {
        redirect('/');
    }

    return <FtmoTerminalView />;
}
