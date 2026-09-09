import { useEffect, useState } from 'react';
import { listRecords } from '../api/records';
import { errorMessage } from '../api/client';

export default function useRecords(resource, params) {
  const [result, setResult] = useState({ results: [], count: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const key = JSON.stringify(params);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    listRecords(resource, JSON.parse(key), controller.signal)
      .then(({ data }) => {
        if (!controller.signal.aborted) setResult(data);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [resource, key, revision]);
  return { ...result, loading, error, reload: () => setRevision((x) => x + 1) };
}
