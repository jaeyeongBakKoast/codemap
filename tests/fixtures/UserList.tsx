import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { UserCard } from './UserCard';
import { Pagination } from './Pagination';

export const UserList: React.FC = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const fetchUsers = async () => {
            setLoading(true);
            const response = await axios.get('/api/users');
            setUsers(response.data);
            setLoading(false);
        };
        fetchUsers();
    }, []);

    const handleDelete = async (id: number) => {
        await axios.delete(`/api/users/${id}`);
    };

    return (
        <div>
            {users.map(user => <UserCard key={user.id} user={user} />)}
            <Pagination />
        </div>
    );
};
