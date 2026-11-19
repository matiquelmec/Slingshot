import { redirect } from 'next/navigation';
import { isBitunixCoreVisible } from '@/shared';
import BitunixTerminalView from './BitunixTerminalView';

export default function BitunixPage() {
    if (!isBitunixCoreVisible()) {
        redirect('/');
    }

    return <BitunixTerminalView />;
}
